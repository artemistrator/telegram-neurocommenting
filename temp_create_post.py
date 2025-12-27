
import asyncio
from backend.directus_client import DirectusClient

async def main():
    d = DirectusClient()
    await d.login()
    try:
        await d.create_item('parsed_posts', {
            'channel_url': 'https://t.me/testkanalcommenting1', 
            'post_id': 123458, 
            'text': 'Manual test post for comment_to 3', 
            'status': 'published',
            'user_created': d.token  # Just to fill if needed, though optional
        })
        print('Created dummy post 123458')
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await d.close()

if __name__ == "__main__":
    asyncio.run(main())
