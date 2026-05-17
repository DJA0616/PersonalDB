"""
Rule-based visualization modules for PersonalDB dashboard.
Generates word clouds, charts, and histograms from normalized message data.
"""
import base64
import io
from collections import Counter
import datetime
import json

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import numpy as np


def fig_to_base64(fig):
    """Convert a matplotlib figure to base64 string."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def generate_wordcloud(messages, per_person=False, person=None):
    """
    Generate word cloud from message content.

    Args:
        messages: List of message dictionaries with 'content' and 'sender_name' keys
        per_person: If True, generate word cloud for specific person
        person: Sender name to filter by (if per_person=True)

    Returns:
        Base64 encoded PNG image string
    """
    if per_person and person:
        filtered_messages = [m for m in messages if m.get('sender_name') == person]
        text = ' '.join([m.get('content', '') for m in filtered_messages if m.get('content')])
        title = f"Word Cloud for {person}"
    else:
        text = ' '.join([m.get('content', '') for m in messages if m.get('content')])
        title = "Overall Word Cloud"

    if not text.strip():
        # Return empty image if no text
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, 'No text data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=16, color='#888888')
        ax.set_title(title, fontsize=18, color='#efefef', pad=20)
        ax.axis('off')
        fig.patch.set_facecolor('#111111')
        return fig_to_base64(fig)

    # Create word cloud
    wordcloud = WordCloud(
        width=800,
        height=400,
        background_color='#0a0a0a',
        colormap='viridis',
        max_words=100,
        relative_scaling=0.5,
        random_state=42
    ).generate(text)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    ax.set_title(title, fontsize=18, color='#efefef', pad=20)
    fig.patch.set_facecolor('#111111')

    return fig_to_base64(fig)


def generate_pie_chart(messages, field, title):
    """
    Generate pie chart for categorical data.

    Args:
        messages: List of message dictionaries
        field: Field to aggregate by (e.g., 'sender_name', 'platform')
        title: Chart title

    Returns:
        Base64 encoded PNG image string
    """
    # Extract field values
    values = [m.get(field, 'Unknown') for m in messages if m.get(field) is not None]
    if not values:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, 'No data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=16, color='#888888')
        ax.set_title(title, fontsize=18, color='#efefef', pad=20)
        ax.axis('off')
        fig.patch.set_facecolor('#111111')
        return fig_to_base64(fig)

    # Count occurrences
    counter = Counter(values)
    labels = list(counter.keys())
    sizes = list(counter.values())

    # Define colors from design system
    colors = ['#7eb8d4', '#a0d4b0', '#f8f8f8', '#c8c8c8', '#888888', '#555555']
    # Repeat colors if needed
    colors = [colors[i % len(colors)] for i in range(len(labels))]

    # Plot
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        autopct='%1.1f%%',
        startangle=90,
        colors=colors,
        textprops={'color': '#0a0a0a', 'fontsize': 12}
    )
    ax.set_title(title, fontsize=18, color='#efefef', pad=20)
    fig.patch.set_facecolor('#111111')

    # Improve legend
    ax.legend(wedges, [f'{l} ({s})' for l, s in zip(labels, sizes)],
              title="Categories", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

    plt.setp(autotexts, size=10, weight="bold")

    return fig_to_base64(fig)


def generate_bar_chart(x_labels, y_values, title, xlabel, ylabel, color='#7eb8d4'):
    """
    Generate bar chart.

    Args:
        x_labels: List of labels for x-axis
        y_values: List of values for y-axis
        title: Chart title
        xlabel: X-axis label
        ylabel: Y-axis label
        color: Bar color (default: accent color)

    Returns:
        Base64 encoded PNG image string
    """
    if not x_labels or not y_values:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=16, color='#888888')
        ax.set_title(title, fontsize=18, color='#efefef', pad=20)
        ax.set_xlabel(xlabel, fontsize=14, color='#c8c8c8')
        ax.set_ylabel(ylabel, fontsize=14, color='#c8c8c8')
        ax.axis('off')
        fig.patch.set_facecolor('#111111')
        return fig_to_base64(fig)

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(x_labels, y_values, color=color, edgecolor='#222222', linewidth=0.5)

    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=10)

    ax.set_title(title, fontsize=18, color='#efefef', pad=20)
    ax.set_xlabel(xlabel, fontsize=14, color='#c8c8c8')
    ax.set_ylabel(ylabel, fontsize=14, color='#c8c8c8')

    # Style
    ax.tick_params(axis='x', colors='#c8c8c8', rotation=45)
    ax.tick_params(axis='y', colors='#c8c8c8')
    ax.spines['bottom'].set_color('#222222')
    ax.spines['top'].set_color('#222222')
    ax.spines['right'].set_color('#222222')
    ax.spines['left'].set_color('#222222')
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#111111')

    plt.tight_layout()

    return fig_to_base64(fig)


def generate_histogram(data, bins=20, title='', xlabel='', ylabel='Count', color='#7eb8d4'):
    """
    Generate histogram.

    Args:
        data: List of numerical values
        bins: Number of bins
        title: Chart title
        xlabel: X-axis label
        ylabel: Y-axis label
        color: Bar color

    Returns:
        Base64 encoded PNG image string
    """
    if not data:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=16, color='#888888')
        ax.set_title(title, fontsize=18, color='#efefef', pad=20)
        ax.set_xlabel(xlabel, fontsize=14, color='#c8c8c8')
        ax.set_ylabel(ylabel, fontsize=14, color='#c8c8c8')
        ax.axis('off')
        fig.patch.set_facecolor('#111111')
        return fig_to_base64(fig)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 6))
    n, bins, patches = ax.hist(data, bins=bins, color=color, edgecolor='#222222', alpha=0.8)

    ax.set_title(title, fontsize=18, color='#efefef', pad=20)
    ax.set_xlabel(xlabel, fontsize=14, color='#c8c8c8')
    ax.set_ylabel(ylabel, fontsize=14, color='#c8c8c8')

    # Style
    ax.tick_params(axis='x', colors='#c8c8c8')
    ax.tick_params(axis='y', colors='#c8c8c8')
    ax.spines['bottom'].set_color('#222222')
    ax.spines['top'].set_color('#222222')
    ax.spines['right'].set_color('#222222')
    ax.spines['left'].set_color('#222222')
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#111111')

    plt.tight_layout()

    return fig_to_base64(fig)


def generate_timeline(dates, counts, title, xlabel='Date', ylabel='Message Count'):
    """
    Generate timeline/area chart.

    Args:
        dates: List of date strings or datetime objects
        counts: List of counts corresponding to dates
        title: Chart title
        xlabel: X-axis label
        ylabel: Y-axis label

    Returns:
        Base64 encoded PNG image string
    """
    if not dates or not counts:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.text(0.5, 0.5, 'No data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=16, color='#888888')
        ax.set_title(title, fontsize=18, color='#efefef', pad=20)
        ax.set_xlabel(xlabel, fontsize=14, color='#c8c8c8')
        ax.set_ylabel(ylabel, fontsize=14, color='#c8c8c8')
        ax.axis('off')
        fig.patch.set_facecolor('#111111')
        return fig_to_base64(fig)

    # Convert dates to datetime if they are strings
    try:
        if isinstance(dates[0], str):
            dates = [datetime.datetime.strptime(d, '%Y-%m-%d') for d in dates]
    except:
        pass  # If conversion fails, use as is

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(dates, counts, color='#7eb8d4', linewidth=2.5)
    ax.fill_between(dates, counts, color='#7eb8d4', alpha=0.3)

    ax.set_title(title, fontsize=18, color='#efefef', pad=20)
    ax.set_xlabel(xlabel, fontsize=14, color='#c8c8c8')
    ax.set_ylabel(ylabel, fontsize=14, color='#c8c8c8')

    # Style
    ax.tick_params(axis='x', colors='#c8c8c8', rotation=45)
    ax.tick_params(axis='y', colors='#c8c8c8')
    ax.spines['bottom'].set_color('#222222')
    ax.spines['top'].set_color('#222222')
    ax.spines['right'].set_color('#222222')
    ax.spines['left'].set_color('#222222')
    ax.set_facecolor('#0a0a0a')
    fig.patch.set_facecolor('#111111')

    plt.tight_layout()

    return fig_to_base64(fig)


def generate_noise_filter_report(original_count, filtered_count, filter_reasons):
    """
    Generate noise filter report as a text-based visualization.

    Args:
        original_count: Original number of messages
        filtered_count: Number of messages after filtering
        filter_reasons: Dictionary of filter reasons and counts

    Returns:
        Base64 encoded PNG image string (text report)
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.axis('off')
    fig.patch.set_facecolor('#111111')

    # Title
    ax.text(0.5, 0.95, 'Noise Filter Report',
            transform=ax.transAxes, fontsize=24, fontweight='bold',
            ha='center', va='top', color='#efefef')

    # Statistics
    filtered_percentage = ((original_count - filtered_count) / original_count * 100) if original_count > 0 else 0

    stats_text = f"""
    Original Messages: {original_count:,}
    Filtered Messages: {filtered_count:,}
    Removed: {original_count - filtered_count:,} ({filtered_percentage:.1f}%)
    """

    ax.text(0.1, 0.8, stats_text,
            transform=ax.transAxes, fontsize=16,
            ha='left', va='top', color='#c8c8c8', fontfamily='monospace')

    # Filter reasons
    if filter_reasons:
        reasons_text = "Filter Reasons:\\n"
        for reason, count in filter_reasons.items():
            percentage = (count / original_count * 100) if original_count > 0 else 0
            reasons_text += f"  • {reason}: {count:,} ({percentage:.1f}%)\\n"

        ax.text(0.1, 0.5, reasons_text,
                transform=ax.transAxes, fontsize=14,
                ha='left', va='top', color='#c8c8c8', fontfamily='monospace')

    return fig_to_base64(fig)


def generate_chunk_size_histogram(chunk_sizes, title='Chunk Size Distribution'):
    """
    Generate histogram for chunk sizes.

    Args:
        chunk_sizes: List of chunk sizes (number of messages per chunk)
        title: Chart title

    Returns:
        Base64 encoded PNG image string
    """
    return generate_histogram(
        data=chunk_sizes,
        bins=max(10, max(chunk_sizes)//2) if chunk_sizes else 10,
        title=title,
        xlabel='Chunk Size (messages per chunk)',
        ylabel='Number of Chunks',
        color='#a0d4b0'
    )


if __name__ == "__main__":
    # Test with sample data
    print("Testing rule-based visualizations...")

    # Sample messages data
    sample_messages = [
        {
            'content': 'Hey, how are you doing today?',
            'sender_name': 'Me',
            'timestamp_ms': 1234567890000,
            'platform': 'instagram'
        },
        {
            'content': 'I\'m good, thanks! How about you?',
            'sender_name': 'Friend',
            'timestamp_ms': 1234567891000,
            'platform': 'instagram'
        },
        {
            'content': 'Just working on some projects.',
            'sender_name': 'Me',
            'timestamp_ms': 1234567892000,
            'platform': 'instagram'
        },
        {
            'content': 'That sounds cool! :)',
            'sender_name': 'Friend',
            'timestamp_ms': 1234567893000,
            'platform': 'instagram'
        },
        {
            'content': 'lol',
            'sender_name': 'Me',
            'timestamp_ms': 1234567894000,
            'platform': 'instagram'
        }
    ] * 20  # Repeat to have more data

    # Test word cloud
    print("Generating word cloud...")
    wc_base64 = generate_wordcloud(sample_messages)
    print(f"Word cloud generated: {len(wc_base64)} characters")

    # Test pie chart
    print("Generating pie chart...")
    pie_base64 = generate_pie_chart(sample_messages, 'sender_name', 'Message Volume by Person')
    print(f"Pie chart generated: {len(pie_base64)} characters")

    # Test bar chart (hourly activity)
    print("Generating bar chart...")
    hours = list(range(24))
    hour_counts = [5, 3, 2, 1, 0, 0, 1, 2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 40, 30, 20, 15, 10, 5]
    bar_base64 = generate_bar_chart(
        [f"{h:02d}:00" for h in hours],
        hour_counts,
        'Messages by Hour of Day',
        'Hour of Day',
        'Message Count'
    )
    print(f"Bar chart generated: {len(bar_base64)} characters")

    # Test histogram (message lengths)
    print("Generating histogram...")
    message_lengths = [len(m['content']) for m in sample_messages if m['content']]
    hist_base64 = generate_histogram(
        message_lengths,
        bins=15,
        title='Message Length Distribution',
        xlabel='Message Length (characters)',
        ylabel='Frequency'
    )
    print(f"Histogram generated: {len(hist_base64)} characters")

    # Test timeline
    print("Generating timeline...")
    from collections import defaultdict
    import datetime
    daily_counts = defaultdict(int)
    for m in sample_messages:
        dt = datetime.datetime.fromtimestamp(m['timestamp_ms'] / 1000)
        date_str = dt.strftime('%Y-%m-%d')
        daily_counts[date_str] += 1
    dates = sorted(daily_counts.keys())
    counts = [daily_counts[d] for d in dates]
    timeline_base64 = generate_timeline(dates, counts, 'Daily Message Activity')
    print(f"Timeline generated: {len(timeline_base64)} characters")

    # Test noise filter report
    print("Generating noise filter report...")
    noise_base64 = generate_noise_filter_report(
        original_count=1000,
        filtered_count=750,
        filter_reasons={
            'Too short (<10 words)': 150,
            'Emoji only': 50,
            'Pure acknowledgement': 30,
            'No content': 20
        }
    )
    print(f"Noise filter report generated: {len(noise_base64)} characters")

    # Test chunk size histogram
    print("Generating chunk size histogram...")
    chunk_sizes = [5, 5, 5, 5, 3, 4, 5, 5, 6, 4, 5, 5, 5, 5, 5] * 10
    chunk_base64 = generate_chunk_size_histogram(chunk_sizes)
    print(f"Chunk size histogram generated: {len(chunk_base64)} characters")

    print("All tests completed!")