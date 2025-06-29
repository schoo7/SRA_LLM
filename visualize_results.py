#!/usr/bin/env python3

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
import warnings
import os
import sys

# Try to import wordcloud, install if not available
try:
    from wordcloud import WordCloud
    WORDCLOUD_AVAILABLE = True
except ImportError:
    print("WARNING: wordcloud not available. Installing...")
    import subprocess
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "wordcloud"])
        from wordcloud import WordCloud
        WORDCLOUD_AVAILABLE = True
        print("✅ wordcloud installed successfully!")
    except Exception as e:
        print(f"❌ Failed to install wordcloud: {e}")
        WORDCLOUD_AVAILABLE = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

def clean_and_count_data(data_series, min_count=2):
    """Clean data and count occurrences, filtering out low-frequency items."""
    # Remove N/A, empty, and null values - handle different data types safely
    cleaned_data = data_series.dropna()
    
    # Convert to string safely and handle non-string data
    try:
        # Convert to string first, then apply string operations
        cleaned_data_str = cleaned_data.astype(str)
        cleaned_data = cleaned_data[cleaned_data_str.str.strip() != '']
        cleaned_data = cleaned_data[cleaned_data_str.str.upper() != 'N/A']
        cleaned_data = cleaned_data[cleaned_data_str.str.strip().str.upper() != 'NAN']
    except (AttributeError, TypeError):
        # If string operations fail, just keep non-null values
        cleaned_data = cleaned_data[cleaned_data.notna()]
    
    # Count occurrences
    counts = cleaned_data.value_counts()
    
    # Filter out items with low counts and group them as "Other"
    main_items = counts[counts >= min_count]
    other_count = counts[counts < min_count].sum()
    
    if other_count > 0:
        main_items['Other (< {} occurrences)'.format(min_count)] = other_count
    
    return main_items

def create_pie_chart(data_counts, title, save_path, max_categories=15):
    """Create a pie chart with improved formatting."""
    if len(data_counts) == 0:
        print(f"⚠️  No data available for {title}")
        return
    
    # Limit to top categories if too many
    if len(data_counts) > max_categories:
        top_data = data_counts.head(max_categories-1)
        other_sum = data_counts.iloc[max_categories-1:].sum()
        if other_sum > 0:
            top_data['Other'] = other_sum
        data_counts = top_data
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Generate colors
    colors = plt.cm.Set3(np.linspace(0, 1, len(data_counts)))
    
    # Create pie chart
    wedges, texts, autotexts = ax.pie(
        data_counts.values, 
        labels=None,  # We'll use legend instead
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        textprops={'fontsize': 9}
    )
    
    # Improve percentage text
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_weight('bold')
    
    # Add legend with counts
    legend_labels = [f"{label} (n={count})" for label, count in data_counts.items()]
    ax.legend(wedges, legend_labels, 
             title="Categories", 
             loc="center left", 
             bbox_to_anchor=(1, 0, 0.5, 1),
             fontsize=9)
    
    # Set title
    ax.set_title(f'{title}\nTotal samples: {data_counts.sum()}', 
                fontsize=14, fontweight='bold', pad=20)
    
    # Equal aspect ratio ensures circular pie chart
    ax.axis('equal')
    
    plt.tight_layout()
    # Save as PNG
    plt.savefig(save_path, dpi=600, bbox_inches='tight')
    # Save as PDF
    pdf_path = save_path.replace('.png', '.pdf')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close()
    
    print(f"✅ Created pie chart: {save_path}")
    print(f"✅ Created PDF version: {pdf_path}")
    print(f"   Top 3 categories: {', '.join(data_counts.head(3).index.tolist())}")

def create_treatment_wordcloud(treatment_data, save_path):
    """Create a word cloud for treatment data."""
    if not WORDCLOUD_AVAILABLE:
        print("❌ WordCloud not available, skipping treatment visualization")
        return
    
    # Clean and process treatment data - handle different data types safely
    cleaned_treatments = treatment_data.dropna()
    
    # Convert to string safely and handle non-string data
    try:
        # Convert to string first, then apply string operations
        cleaned_treatments_str = cleaned_treatments.astype(str)
        cleaned_treatments = cleaned_treatments[cleaned_treatments_str.str.strip() != '']
        cleaned_treatments = cleaned_treatments[cleaned_treatments_str.str.upper() != 'N/A']
        cleaned_treatments = cleaned_treatments[cleaned_treatments_str.str.strip().str.upper() != 'NAN']
    except (AttributeError, TypeError):
        # If string operations fail, just keep non-null values and convert to string
        cleaned_treatments = cleaned_treatments[cleaned_treatments.notna()].astype(str)
    
    if len(cleaned_treatments) == 0:
        print("⚠️  No treatment data available for word cloud")
        return
    
    # Process treatments to extract individual treatment terms
    all_treatments = []
    for treatment in cleaned_treatments:
        # Remove symbols and clean text
        import re
        # Remove quotes, commas, parentheses, brackets, and other punctuation
        cleaned_text = re.sub(r'["\',\(\)\[\]\.;:!?`~@#$%^&*={}|\\/<>]', ' ', str(treatment))
        # Split by common separators and clean
        treatments = cleaned_text.replace('+', ' ').replace('_', ' ').replace('-', ' ')
        treatment_words = [word.strip() for word in treatments.split() if len(word.strip()) > 2]
        all_treatments.extend(treatment_words)
    
    # Count frequency
    treatment_counts = Counter(all_treatments)
    
    # Remove very common but uninformative words (expanded list)
    stop_words = {
        'control', 'treated', 'treatment', 'with', 'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'by',
        'cells', 'cell', 'line', 'sample', 'samples', 'experiment', 'study', 'analysis', 'data', 'using', 'from', 'this',
        'that', 'these', 'those', 'was', 'were', 'been', 'being', 'have', 'has', 'had', 'will', 'would', 'could', 'should',
        'may', 'might', 'can', 'are', 'is', 'be', 'do', 'does', 'did', 'done', 'up', 'down', 'out', 'off', 'over', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 'just', 'now', 'during', 'before', 'after', 'above', 'below', 'between', 'into', 'through', 'against',
        'rep', 'replicate', 'replicates', 'biological', 'technical', 'day', 'days', 'hour', 'hours', 'time', 'times',
        'condition', 'conditions', 'group', 'groups', 'set', 'sets', 'type', 'types', 'level', 'levels', 'dose', 'concentration',
        'protocol', 'however', 'but', 'mention', 'mentions', 'instruction', 'includes', 'part', 'weeks', 'week', 'says', 'say', 'treatment:', "it's",
        "user's", 'knock', 'characteristics', 'However', 'which', 'maybe', 'loop', 'use', 'terms', 'examples'
    }
    treatment_counts = {k: v for k, v in treatment_counts.items() if k.lower() not in stop_words}
    
    if not treatment_counts:
        print("⚠️  No meaningful treatment terms found for word cloud")
        return
    
    # Create word cloud
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    
    # Word cloud
    wordcloud = WordCloud(
        width=800, 
        height=600, 
        background_color='white',
        max_words=100,
        colormap='viridis',
        relative_scaling=0.5
    ).generate_from_frequencies(treatment_counts)
    
    ax1.imshow(wordcloud, interpolation='bilinear')
    ax1.axis('off')
    ax1.set_title('Treatment Word Cloud', fontsize=16, fontweight='bold')
    
    # Bar chart of top treatments
    top_treatments = dict(Counter(treatment_counts).most_common(15))
    if top_treatments:
        bars = ax2.bar(range(len(top_treatments)), list(top_treatments.values()), 
                      color=plt.cm.viridis(np.linspace(0, 1, len(top_treatments))))
        ax2.set_xticks(range(len(top_treatments)))
        ax2.set_xticklabels(list(top_treatments.keys()), rotation=45, ha='right')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Top Treatment Terms', fontsize=16, fontweight='bold')
        ax2.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for bar, value in zip(bars, top_treatments.values()):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{value}', ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    # Save as PNG
    plt.savefig(save_path, dpi=600, bbox_inches='tight')
    # Save as PDF
    pdf_path = save_path.replace('.png', '.pdf')
    plt.savefig(pdf_path, format='pdf', bbox_inches='tight')
    plt.close()
    
    print(f"✅ Created treatment word cloud: {save_path}")
    print(f"✅ Created PDF version: {pdf_path}")
    top_3_treatments = [item[0] for item in Counter(treatment_counts).most_common(3)]
    print(f"   Top 3 treatments: {', '.join(top_3_treatments)}")

def generate_summary_stats(df, output_path):
    """Generate a summary statistics file."""
    with open(output_path, 'w') as f:
        f.write("SRA/GEO Results Analysis Summary\n")
        f.write("=" * 50 + "\n\n")
        
        f.write(f"Total samples: {len(df)}\n\n")
        
        # Analyze each column
        columns_to_analyze = [
            'species', 'sequencing_technique', 'sample_type', 'cell_line_name',
            'tissue_type', 'disease_description', 'treatment', 
            'is_chipseq_related_experiment', 'chipseq_antibody_target'
        ]
        
        for col in columns_to_analyze:
            if col in df.columns:
                f.write(f"{col.upper()}:\n")
                
                # Count non-N/A values - handle different data types safely
                valid_data = df[col].dropna()
                
                # Convert to string safely and handle non-string data
                try:
                    # Convert to string first, then apply string operations
                    valid_data_str = valid_data.astype(str)
                    valid_data = valid_data[valid_data_str.str.strip() != '']
                    valid_data = valid_data[valid_data_str.str.upper() != 'N/A']
                    valid_data = valid_data[valid_data_str.str.strip().str.upper() != 'NAN']
                except (AttributeError, TypeError):
                    # If string operations fail, just remove obvious empty/null values
                    valid_data = valid_data[valid_data.notna()]
                    # For numeric columns, no need for string operations
                    pass
                
                f.write(f"  Valid entries: {len(valid_data)} ({len(valid_data)/len(df)*100:.1f}%)\n")
                f.write(f"  Missing/N/A: {len(df) - len(valid_data)} ({(len(df) - len(valid_data))/len(df)*100:.1f}%)\n")
                
                if len(valid_data) > 0:
                    unique_values = valid_data.nunique()
                    f.write(f"  Unique values: {unique_values}\n")
                    
                    # Top 5 most common values
                    top_values = valid_data.value_counts().head(5)
                    f.write(f"  Top values:\n")
                    for value, count in top_values.items():
                        f.write(f"    {value}: {count} ({count/len(valid_data)*100:.1f}%)\n")
                
                f.write("\n")
    
    print(f"✅ Generated summary statistics: {output_path}")

def main():
    """Main function to generate all visualizations."""
    import sys
    
    # Accept input file as command line argument
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = 'result_prompt_fallback.csv'  # Default fallback
    
    output_dir = 'visualizations'
    
    print("🎨 SRA/GEO Results Visualization Generator")
    print("=" * 50)
    print(f"📖 Input file: {input_file}")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: {input_file} not found!")
        return
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Read data
    print(f"📖 Reading data from {input_file}...")
    try:
        df = pd.read_csv(input_file)
        print(f"✅ Loaded {len(df)} samples with {len(df.columns)} columns")
        print(f"   Columns: {', '.join(df.columns.tolist())}")
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return
    
    # Generate summary statistics
    print("\n📊 Generating summary statistics...")
    summary_path = os.path.join(output_dir, 'summary_statistics.txt')
    generate_summary_stats(df, summary_path)
    
    # Define columns for pie charts (excluding IDs and summary)
    pie_chart_columns = {
        'species': 'Species Distribution',
        'sequencing_technique': 'Sequencing Technique Distribution', 
        'sample_type': 'Sample Type Distribution',
        'cell_line_name': 'Cell Line Distribution',
        'tissue_type': 'Tissue Type Distribution',
        'disease_description': 'Disease Description Distribution',
        'is_chipseq_related_experiment': 'ChIP-seq Related Experiments',
        'chipseq_antibody_target': 'ChIP-seq Antibody Targets'
    }
    
    # Generate pie charts
    print("\n🥧 Generating pie charts...")
    for column, title in pie_chart_columns.items():
        if column in df.columns:
            print(f"   Processing: {column}")
            data_counts = clean_and_count_data(df[column])
            save_path = os.path.join(output_dir, f'{column}_pie_chart.png')
            create_pie_chart(data_counts, title, save_path)
        else:
            print(f"⚠️  Column '{column}' not found in data")
    
    # Generate treatment word cloud
    print("\n☁️  Generating treatment word cloud...")
    if 'treatment' in df.columns:
        treatment_path = os.path.join(output_dir, 'treatment_wordcloud.png')
        create_treatment_wordcloud(df['treatment'], treatment_path)
    else:
        print("⚠️  Treatment column not found in data")
    
    print(f"\n✅ All visualizations completed!")
    print(f"📁 Output directory: {output_dir}")
    print(f"📊 Generated files (PNG + PDF formats):")
    
    # List generated files
    for file in sorted(os.listdir(output_dir)):
        file_path = os.path.join(output_dir, file)
        file_size = os.path.getsize(file_path)
        if file.endswith('.png'):
            print(f"   🖼️  {file} ({file_size/1024:.1f} KB)")
        elif file.endswith('.pdf'):
            print(f"   📄 {file} ({file_size/1024:.1f} KB)")
        else:
            print(f"   📊 {file} ({file_size/1024:.1f} KB)")

if __name__ == "__main__":
    main() 