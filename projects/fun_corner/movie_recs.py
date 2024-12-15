import time
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler, MultiLabelBinarizer
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, silhouette_samples
import os
from pathlib import Path

def assign_time_period(date):
    if pd.isna(date):
        return "Unknown"
    try:
        year = pd.to_datetime(date).year
        
        # More precise period assignments
        if year <= 1969:
            return "Pre-1970s"
        elif 1970 <= year <= 1982:  # Early 70s to Early 80s
            return "1970s-1980s"
        elif 1983 <= year <= 1994:  # Mid 80s to Early 90s
            return "1980s-1990s"
        elif 1995 <= year <= 2009:  # Mid 90s to Late 2000s
            return "1990s-2000s"
        elif 2010 <= year <= 2024:
            return "2010s-Present"
        else:
            return "Upcoming"
    except:
        return "Unknown"

def create_optimized_clusters(df, n_clusters=12):
    """Create content clusters with optimized weights and clustering metrics"""
    print("Preparing content-based features...")
    
    # Convert genres to string if it's a list
    df['genres'] = df['genres'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
    
    # Create genres list after ensuring string format
    df['genres_list'] = df['genres'].fillna('Unknown').str.split(', ')
    df['time_period'] = df['first_air_date'].apply(assign_time_period)
    
    # Now create features
    mlb = MultiLabelBinarizer()
    genre_matrix = mlb.fit_transform(df['genres_list'])
    
    # Apply optimized weights
    scaler = StandardScaler()
    genre_scaled = scaler.fit_transform(pd.DataFrame(genre_matrix)) * 1.0
    media_scaled = scaler.fit_transform(pd.get_dummies(df[['media_type']])) * 1.0
    lang_scaled = scaler.fit_transform(pd.get_dummies(df[['original_language']])) * 4.0
    time_scaled = scaler.fit_transform(pd.get_dummies(df[['time_period']])) * 0.5
    
    X = np.concatenate([genre_scaled, media_scaled, lang_scaled, time_scaled], axis=1)
    
    print(f"\nCreating {n_clusters} clusters...")
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=50)
    cluster_labels = kmeans.fit_predict(X)
    
    # Calculate clustering quality metrics
    silhouette_avg = silhouette_score(X, cluster_labels)
    print(f"\nClustering Quality:")
    print(f"Average Silhouette Score: {silhouette_avg:.3f}")
    
    df['Cluster'] = cluster_labels
    return df, X, kmeans

def get_optimized_recommendations(df_clustered, X, query_params, n_recommendations=12):
    start_time = time.time()
    
    # Calculate silhouette scores first
    cluster_silhouette_avg = silhouette_score(X, df_clustered['Cluster'])
    sample_silhouette_values = silhouette_samples(X, df_clustered['Cluster'])
    
    # Get cluster-specific scores
    cluster_scores = {}
    for cluster in df_clustered['Cluster'].unique():
        mask = df_clustered['Cluster'] == cluster
        if sum(mask) > 1:
            cluster_scores[cluster] = sample_silhouette_values[mask].mean()
    
    # Initial filtering
    mask = pd.Series(True, index=df_clustered.index)
    
    # Apply all filters
    if 'media_type' in query_params and query_params['media_type'] != 'any':
        mask &= df_clustered['media_type'] == query_params['media_type']
    
    if 'language' in query_params and query_params['language'] != 'any':
        mask &= df_clustered['original_language'] == query_params['language']
        
    if 'time_period' in query_params and query_params['time_period'] != 'any':
        mask &= df_clustered['time_period'] == query_params['time_period']
    
    filtered_df = df_clustered[mask].copy()
    
    # Check if we have any results after initial filtering
    if len(filtered_df) == 0:
        metrics = {
            'execution_time': f"{time.time() - start_time:.3f} seconds",
            'total_matches': 0,
            'recommendations_found': 0
        }
        return [], metrics
    
    # Add genre filtering if specified
    if 'genres' in query_params and query_params['genres'] != 'any':
        genre_query = query_params['genres'].lower()
        
        # First find exact matches
        exact_matches = filtered_df[
            filtered_df['genres'].astype(str).str.lower().apply(
                lambda x: genre_query in x
            )
        ]
        
        # If few exact matches, look for related genres
        if len(exact_matches) < 5 and len(exact_matches) > 0:  # Only if we have some matches
            relevant_clusters = exact_matches['Cluster'].unique()
            
            related_genres = {
                'Horror': ['Thriller', 'Mystery'],
                'Action': ['Adventure', 'Thriller'],
                'Comedy': ['Family', 'Romance'],
                'Drama': ['Romance', 'Family'],
                'Science Fiction': ['Fantasy', 'Adventure'],
                'Fantasy': ['Adventure', 'Science Fiction'],
                'Romance': ['Drama', 'Comedy']
            }
            
            similar_genres = related_genres.get(query_params['genres'], [])
            
            if similar_genres:  # Only if we have related genres
                genre_mask = (
                    filtered_df['Cluster'].isin(relevant_clusters) &
                    filtered_df['genres'].astype(str).str.lower().apply(
                        lambda x: any(g.lower() in x for g in similar_genres)
                    )
                )
                
                similar_matches = filtered_df[genre_mask]
                all_indices = set(exact_matches.index) | set(similar_matches.index)
                filtered_df = df_clustered.loc[list(all_indices)].copy()
        else:
            filtered_df = exact_matches
            
        if len(filtered_df) > 0:  # Only add scores if we have results
            filtered_df['relevance_score'] = filtered_df.apply(
                lambda x: 8.0 if genre_query in str(x['genres']).lower() else 7.0, axis=1
            )
        else:
            metrics = {
                'execution_time': f"{time.time() - start_time:.3f} seconds",
                'total_matches': 0,
                'recommendations_found': 0
            }
            return [], metrics
    else:
        # For non-genre queries, base relevance on popularity
        filtered_df['relevance_score'] = 6.0  # Base score
    
    # Calculate metrics
    metrics = {
        'execution_time': f"{time.time() - start_time:.3f} seconds",
        'total_matches': len(filtered_df),
        'recommendations_found': min(len(filtered_df), n_recommendations)
    }
    
    if len(filtered_df) > 0:
        recommendations = filtered_df.nlargest(n_recommendations, ['relevance_score', 'popularity'])
        
        # Print all analysis
        print("\nClustering Quality:")
        print(f"Overall Silhouette Score: {cluster_silhouette_avg:.3f}")
        
        print("\nCluster-specific Silhouette Scores:")
        for cluster, score in cluster_scores.items():
            print(f"Cluster {cluster}: {score:.3f}")
        
        print("\nPerformance Metrics:")
        for key, value in metrics.items():
            print(f"{key}: {value}")
        
        print("\nCluster Distribution in Recommendations:")
        print(recommendations['Cluster'].value_counts())
        
        print("\nRecommended content:")
        for _, rec in recommendations.iterrows():
            print(f"\nTitle: {rec['name']}")
            print(f"Genres: {rec['genres']}")
            print(f"Type: {rec['media_type']}")
            print(f"Language: {rec['original_language']}")
            print(f"Time Period: {rec['time_period']}")
            print(f"Popularity: {rec['popularity']:.2f}")
            print(f"Relevance Score: {rec['relevance_score']:.2f}")
            print(f"Cluster: {rec['Cluster']} (Silhouette Score: {cluster_scores.get(rec['Cluster'], 'N/A'):.3f})")
            print("-" * 50)
        
        return recommendations[['name', 'genres', 'media_type', 'original_language', 
                              'popularity', 'poster_path']].to_dict('records'), metrics
    
    return [], metrics

# Only load data when running directly
if __name__ == "__main__":
    # Get the correct path to CSV
    base_dir = Path(__file__).resolve().parent
    csv_path = os.path.join(base_dir, 'data', 'tmdb_all_media.csv')
    
    # Load and preprocess data
    df = pd.read_csv(csv_path)
    
    # Convert genres to string format immediately after loading
    df['genres'] = df['genres'].fillna('Unknown')
    df['genres'] = df['genres'].apply(
        lambda x: ', '.join(eval(x)) if isinstance(x, str) and x.startswith('[') else x
    )
    
    # Your test query
    query = {
        'genres': 'Action',  
        'language': 'English',
        'time_period': '2010s-Present',
        'media_type': 'tv'
    }

    print("Creating clusters...")
    df_clustered, X, kmeans = create_optimized_clusters(df)
    
    print("\nGetting recommendations...")
    recommendations, metrics = get_optimized_recommendations(df_clustered, X, query)





