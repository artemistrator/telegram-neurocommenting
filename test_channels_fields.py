import asyncio
import os
from backend.directus_client import directus

async def test_channels_fields():
    """Test what fields are available in the channels collection"""
    print("=== Testing Available Fields in Channels Collection ===\n")
    
    try:
        # Login first
        print("1. Logging into Directus...")
        await directus.login()
        print("Directus login successful")
        
        # Get collection schema to see what fields exist
        print("\n2. Getting channels collection schema...")
        try:
            response = await directus.client.get("/collections/channels")
            print(f"Collection schema status: {response.status_code}")
            if response.status_code == 200:
                schema = response.json()
                print(f"Collection schema: {schema}")
                
                # Get fields for the channels collection
                fields_response = await directus.client.get("/fields/channels")
                print(f"\n3. Getting channels fields...")
                print(f"Fields status: {fields_response.status_code}")
                if fields_response.status_code == 200:
                    fields = fields_response.json()
                    print(f"Available fields in channels collection:")
                    for field in fields.get('data', []):
                        field_name = field.get('field')
                        field_type = field.get('type')
                        print(f"  - {field_name} ({field_type})")
                        
                    # Check if the problematic fields exist
                    field_names = [f.get('field') for f in fields.get('data', [])]
                    missing_fields = ['last_comment_date', 'comments_count']
                    for field in missing_fields:
                        if field not in field_names:
                            print(f"\n❌ Field '{field}' does NOT exist in the collection!")
                        else:
                            print(f"\n✅ Field '{field}' exists in the collection")
                else:
                    print(f"Failed to get fields: {fields_response.text}")
            else:
                print(f"Failed to get collection schema: {response.text}")
        except Exception as e:
            print(f"Error getting schema: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_channels_fields())