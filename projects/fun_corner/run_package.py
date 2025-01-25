from tmdb_fetcher import get_tmdb_csv
from boxoffice_fetcher import get_boxoffice_csv,get_theatrical_csv

def main():
    print("\n1. Getting TMDB data...")
    tmdb_file = get_tmdb_csv()
    print(f"✅ TMDB data saved to: {tmdb_file}")
    
    #print("\n2. Getting theatrical releases...")
    #theatrical_file = get_theatrical_csv()
    #print(f"✅ Theatrical data saved to: {theatrical_file}")
    
    #print("\n3. Getting distributor earnings...")
    #earnings_file = get_boxoffice_csv()
    #print(f"✅ Earnings data saved to: {earnings_file}")
    
    print("\n✨ All data fetching completed!")

if __name__ == "__main__":
    main()