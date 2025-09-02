#!/usr/bin/env python3
"""
Direct test of Duffel API to verify API key and basic functionality.

This script replicates the curl command to test flight search directly
against the Duffel API without going through the MCP server.
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/Users/pdwivedi/Documents/Projects/flight_agent/.env')

def test_duffel_api():
    """Test Duffel API with a basic flight search request."""
    
    # Get API key from environment
    api_key = os.getenv("DUFFEL_API_KEY_LIVE") or os.getenv("DUFFEL_API_KEY")
    
    if not api_key:
        print("❌ Error: No Duffel API key found in environment variables")
        print("Please set DUFFEL_API_KEY_LIVE or DUFFEL_API_KEY in your .env file")
        return False
    
    print(f"🔑 Using API key: {api_key[:15]}..." if len(api_key) > 15 else api_key)
    print("🧪 Testing Duffel API directly...")
    print("=" * 60)
    
    # API endpoint
    url = "https://api.duffel.com/air/offer_requests"
    
    # Headers (replicating the curl command)
    headers = {
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip",
        "Duffel-Version": "v2",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Request payload (replicating the curl command with updated date)
    payload = {
        "data": {
            "cabin_class": "economy",
            "slices": [
                {
                    "departure_date": "2025-09-15",  # Updated to valid future date
                    "destination": "LAX",            # Changed to LAX for SFO->LAX test
                    "origin": "SFO"                  # Changed to SFO
                }
            ],
            "passengers": [
                {
                    "type": "adult"
                }
            ]
        }
    }
    
    print(f"🛫 Searching flights: SFO → LAX on 2025-09-15")
    print(f"📊 Request payload:")
    print(json.dumps(payload, indent=2))
    print()
    
    try:
        # Make the API request
        print("🚀 Making API request...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        print(f"📈 Response Status: {response.status_code}")
        print(f"📝 Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code in [200, 201]:
            status_msg = "200 OK" if response.status_code == 200 else "201 Created (offer request created)"
            print(f"✅ API request successful! ({status_msg})")
            
            # Parse the response
            data = response.json()
            
            # Display basic info about the response
            if 'data' in data:
                print(f"📋 Request ID: {data['data'].get('id', 'N/A')}")
                print(f"🔄 Live Mode: {data['data'].get('live_mode', 'N/A')}")
                
                # Check for offers
                offers = data['data'].get('offers', [])
                print(f"✈️  Found {len(offers)} flight offers")
                
                if offers:
                    print("\n🎯 Sample offers:")
                    for i, offer in enumerate(offers[:3]):  # Show first 3 offers
                        price = offer.get('total_amount', 'N/A')
                        currency = offer.get('total_currency', 'N/A')
                        print(f"  {i+1}. Price: {price} {currency}")
                        
                        # Show flight details
                        slices = offer.get('slices', [])
                        for slice_info in slices:
                            origin = slice_info.get('origin', {}).get('iata_code', 'N/A')
                            destination = slice_info.get('destination', {}).get('iata_code', 'N/A')
                            duration = slice_info.get('duration', 'N/A')
                            print(f"     Route: {origin} → {destination}, Duration: {duration}")
                else:
                    print("ℹ️  No flight offers returned (this might be normal for test API keys)")
            
            # Save full response for detailed inspection
            with open('duffel_api_response.json', 'w') as f:
                json.dump(data, f, indent=2)
            print(f"\n💾 Full response saved to 'duffel_api_response.json'")
            
            return True
            
        elif response.status_code == 401:
            print("❌ Authentication failed!")
            print("🔑 Please check your API key is correct and active")
            print(f"💭 API key used: {api_key[:15]}...")
            return False
            
        elif response.status_code == 400:
            print("❌ Bad request!")
            try:
                error_data = response.json()
                print("🔍 Error details:")
                print(json.dumps(error_data, indent=2))
            except:
                print(f"🔍 Raw response: {response.text}")
            return False
            
        else:
            print(f"❌ Unexpected response status: {response.status_code}")
            print("ℹ️  Expected: 200 (OK) or 201 (Created)")
            print(f"🔍 Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (30s)")
        print("🌐 Check your internet connection")
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {str(e)}")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def test_api_key_format():
    """Test if the API key has the expected format."""
    
    api_key = os.getenv("DUFFEL_API_KEY_LIVE") or os.getenv("DUFFEL_API_KEY")
    
    if not api_key:
        return False
    
    print("🔍 API Key Analysis:")
    print(f"   Length: {len(api_key)} characters")
    print(f"   Starts with: {api_key[:10]}...")
    print(f"   Format check: {'✅ Looks like Duffel key' if api_key.startswith('duffel_') else '⚠️  Unexpected format'}")
    
    if api_key == 'duffel_test':
        print("   Type: Basic test key")
    elif 'test' in api_key.lower():
        print("   Type: Enhanced test key")  
    else:
        print("   Type: Live key")
    
    print()
    return True

def main():
    """Main test function."""
    
    print("🧪 === Duffel API Direct Test ===")
    print("Testing API connectivity before MCP integration")
    print()
    
    # Test API key format
    if not test_api_key_format():
        print("❌ No API key found. Please set DUFFEL_API_KEY_LIVE in your .env file")
        return
    
    # Test API functionality
    success = test_duffel_api()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Duffel API test completed successfully!")
        print("✅ Your API key is working correctly")
        print("🚀 Ready to proceed with MCP integration")
    else:
        print("❌ Duffel API test failed")
        print("🔧 Please check your API key and try again")
    
    print()
    print("💡 Next steps:")
    if success:
        print("   - Run the flight MCP agent: python flight_mcp_test.py")
        print("   - Try different flight searches")
    else:
        print("   - Verify your API key in the .env file")
        print("   - Check Duffel documentation for API key setup")
        print("   - Try with 'duffel_test' for basic testing")

if __name__ == "__main__":
    main()
