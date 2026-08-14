SCRAPE_CHANNEL_ID = -1004322090872  # Your secret channel ID

async def scrape_secret_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Passively listens to the secret group and saves any cards posted."""
    if update.effective_chat.id != SCRAPE_CHANNEL_ID:
        return
        
    text = update.message.text or update.message.caption or ""
    found_cards = []
    
    if update.message.document:
        try:
            doc = update.message.document
            file = await doc.get_file()
            content = (await file.download_as_bytearray()).decode("utf-8", errors="ignore")
            found_cards = re.findall(r'\b\d{13,19}\s*[|/:=]\s*\d{1,2}\s*[|/:=]\s*\d{2,4}\s*[|/:=]\s*\d{3,4}\b', content)
            if not found_cards:
                found_cards = [c.strip() for c in content.split() if "|" in c]
        except:
            pass
    else:
        found_cards = re.findall(r'\b\d{13,19}\s*[|/:=]\s*\d{1,2}\s*[|/:=]\s*\d{2,4}\s*[|/:=]\s*\d{3,4}\b', text)
        if not found_cards:
            found_cards = [c.strip() for c in text.split() if "|" in c]
            
    if found_cards:
        if 'scraped_cards_buffer' not in context.bot_data:
            context.bot_data['scraped_cards_buffer'] = []
        context.bot_data['scraped_cards_buffer'].extend(found_cards)
        logging.info(f"Scraped {len(found_cards)} cards from secret group. Total buffer: {len(context.bot_data['scraped_cards_buffer'])}")

async def generate_and_send_cards(update: Update, context: ContextTypes.DEFAULT_TYPE, cards: list, cards_per_file: int):
    SECRET_CHANNEL_ID = -1004322090872
    total_cards = len(cards)
    if total_cards == 0:
        await update.message.reply_text("❌ No valid cards found to process.", parse_mode="HTML")
        return
        
    total_files = (total_cards + cards_per_file - 1) // cards_per_file
    status_msg = await update.message.reply_text(f"⏳ Processing {total_cards} scraped cards into {total_files} files...", parse_mode="HTML")
    
    file_count = 0
    for i in range(0, total_cards, cards_per_file):
        chunk = cards[i:i + cards_per_file]
        lines = [
            "┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉",
            f"File {file_count + 1} of {total_files}",
            f"Cards per file: {cards_per_file}",
            f"Total Cards in this file: {len(chunk)}",
            "┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉",
            ""
        ]
        
        for card in chunk:
            bin_num = card[:6]
            try:
                bin_data = await asyncio.wait_for(_bin_lookup(bin_num), timeout=5)
            except:
                bin_data = {}
            bin_info_str = _bin_str_plain(bin_data)
            lines += [
                f"Card ➳ {card}",
                f"Bin ➳ {bin_info_str}",
                "┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉"
            ]
            
        content = "\n".join(lines)
        buf = BytesIO(content.encode("utf-8"))
        buf.seek(0)
        file_count += 1
        filename = f"Superman_Cards_{file_count}_of_{total_files}.txt"
        
        # Send ONLY to the Secret Channel (since the command only works there anyway)
        try:
            await context.bot.send_document(
                chat_id=SECRET_CHANNEL_ID, 
                document=InputFile(buf, filename=filename), 
                caption=f"<b>📄 Cards File {file_count}/{total_files}</b>\n<b>Cards:</b> {len(chunk)}", 
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Error sending file to secret channel: {e}")
            
        await asyncio.sleep(0.5)
        
    await status_msg.edit_text(f"✅ Done! {total_cards} cards split into {total_files} files.")

async def cmd_cards(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SECRET_CHANNEL_ID = -1004322090872
    
    # 1. Only Owner can use
    if update.effective_user.id != OWNER_ID:
        return
        
    # 2. ONLY works in the Secret Channel
    if update.effective_chat.id != SECRET_CHANNEL_ID:
        await update.message.reply_text("❌ This command can only be used inside the secret channel.", parse_mode="HTML")
        return
        
    if not context.args:
        await update.message.reply_text(
            "<b>📄 Card Splitter</b>\n"
            "┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉\n"
            "<b>Usage:</b>\n"
            "<code>/cards N</code> (where N is cards per file)\n\n"
            "<b>Example:</b> <code>/cards 50</code>\n\n"
            "<i>The bot automatically scrapes cards posted in this secret group. "
            "Use this command to pack them into files.</i>\n"
            "┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉", 
            parse_mode="HTML"
        )
        return
        
    try:
        cards_per_file = int(context.args[0])
        if cards_per_file <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ N must be a positive number.", parse_mode="HTML")
        return
        
    # Get scraped cards from the secret group memory
    cards = context.bot_data.get('scraped_cards_buffer', [])
    
    if not cards:
        await update.message.reply_text("❌ No cards found in the buffer. Send some cards to this secret group first.", parse_mode="HTML")
        return
        
    # Clear the buffer
    context.bot_data['scraped_cards_buffer'] = []
    
    # Generate and send
    await generate_and_send_cards(update, context, cards, cards_per_file)
