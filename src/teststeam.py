import requests

def test_steam_connection():
    # Testing with a popular age-restricted game (Baldur's Gate 3)
    url = "https://store.steampowered.com/app/1086940/" 
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Steam doesn't use Cloudflare, but it does use an age-gate for mature games.
    # Passing these cookies bypasses the "Enter your birthdate" redirect.
    cookies = {
        "birthtime": "283993201",
        "lastagecheckage": "1-0-1979"
    }

    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Extract the title tag to prove we bypassed any challenge pages
            if "<title>" in response.text:
                title = response.text.split("<title>")[1].split("</title>")[0]
                print(f"Success! Extracted Title: {title.strip()}")
            else:
                print("Status 200, but no title tag found. Check the raw HTML.")
        else:
            print("Blocked or encountered an error.")
            
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    test_steam_connection()