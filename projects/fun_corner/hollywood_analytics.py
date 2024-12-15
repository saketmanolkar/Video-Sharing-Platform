import pandas as pd
import os
from django.conf import settings
import traceback

def load_box_office_data():
    """Load and process the box office data"""
    # Define the path relative to your project root
    csv_path = os.path.join(settings.BASE_DIR, 'projects', 'fun_corner', 'data', 'combined_monthly_earnings.csv')
    df = pd.read_csv(csv_path)
    return df

def clean_currency(value):
    """Convert currency string to float"""
    if isinstance(value, str):
        return float(value.replace('$', '').replace(',', ''))
    return float(value)

def get_major_studios_data():
    """Get monthly data for major studios and total industry"""
    df = load_box_office_data()
    
    major_studios = [
        'Warner Bros.',
        'Universal Pictures',
        'Paramount Pictures',
        'Sony Pictures Releasing',
        'Walt Disney Studios Motion Pictures',
        'Total Industry Earnings'
    ]
    
    # Filter for major studios
    filtered_df = df[df['Distributor'].isin(major_studios)].copy()  # Create a copy to avoid SettingWithCopyWarning
    
    # Clean currency values for all columns except 'Distributor'
    for col in filtered_df.columns:
        if col != 'Distributor':
            filtered_df[col] = filtered_df[col].apply(clean_currency)
    
    # Format data for Chart.js with colors
    datasets = []
    colors = {
        'Warner Bros.': 'rgb(77, 171, 247)',
        'Universal Pictures': 'rgb(255, 128, 155)',
        'Paramount Pictures': 'rgb(255, 177, 101)',
        'Sony Pictures Releasing': 'rgb(255, 212, 96)',
        'Walt Disney Studios Motion Pictures': 'rgb(111, 207, 203)',
        'Total Industry Earnings': 'rgb(156, 136, 255)'
    }
    
    for studio in major_studios:
        if studio in filtered_df['Distributor'].values:
            studio_data = filtered_df[filtered_df['Distributor'] == studio].iloc[0, 1:]
            datasets.append({
                'label': studio,
                'data': list(studio_data),
                'borderColor': colors[studio],
                'backgroundColor': colors[studio],
                'fill': False,
                'tension': 0.3,
                'borderWidth': 2,
                'pointRadius': 4
            })
    
    return {
        'labels': list(filtered_df.columns[1:]),  # All months
        'datasets': datasets
    }

def get_current_movies_data():
    """Get current movies performance data"""
    try:
        df = pd.read_csv('projects/fun_corner/data/movies_with_paths.csv')
        
        df['Daily_Gross_Num'] = (df['Daily Gross']
            .str.replace('$', '', regex=False)
            .str.replace(',', '', regex=False)
            .astype(float))
        top_movies = df.nlargest(5, 'Daily_Gross_Num')
        
        data = {
            'titles': top_movies['Title'].tolist(),
            'daily_gross': top_movies['Daily_Gross_Num'].tolist(),
            'posters': top_movies['poster_path'].tolist()  # Just the poster paths
        }
        return data
        
    except Exception as e:
        print(f"Error in get_current_movies_data: {str(e)}")
        traceback.print_exc()
        return {
            'titles': [],
            'daily_gross': [],
            'posters': []
        }