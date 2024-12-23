import os
from telegram import Bot
from telegram.constants import StickerFormat
import asyncio
from config import BOT_TOKEN

async def create_animated_sticker_set():
    bot = Bot(token=BOT_TOKEN)
    
    # Create sticker set name (must end in '_by_your_bot')
    sticker_set_name = "animated_neet_by_your_bot"
    sticker_set_title = "Animated NEET Memecoin"
    
    # Directory containing your WebM sticker files
    stickers_dir = "animated_stickers"
    
    try:
        # Get all WebM files from the stickers directory
        sticker_files = [f for f in os.listdir(stickers_dir) if f.endswith('.webm')]
        
        # Create sticker set with first sticker
        first_sticker = open(os.path.join(stickers_dir, sticker_files[0]), 'rb')
        await bot.create_new_sticker_set(
            user_id=YOUR_USER_ID,  # Replace with your Telegram user ID
            name=sticker_set_name,
            title=sticker_set_title,
            stickers=[{
                'sticker': first_sticker,
                'emoji_list': ['🚀']
            }],
            sticker_format=StickerFormat.ANIMATED
        )
        
        # Add remaining stickers
        for sticker_file in sticker_files[1:]:
            with open(os.path.join(stickers_dir, sticker_file), 'rb') as f:
                await bot.add_sticker_to_set(
                    user_id=YOUR_USER_ID,
                    name=sticker_set_name,
                    sticker={
                        'sticker': f,
                        'emoji_list': ['🚀']
                    }
                )
        
        print(f"Successfully created animated sticker pack: t.me/addstickers/{sticker_set_name}")
        
    except Exception as e:
        print(f"Error creating sticker pack: {e}")

if __name__ == "__main__":
    asyncio.run(create_animated_sticker_set())
