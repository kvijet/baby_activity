import plotly.graph_objects as go


def create_24hour_timeline(df_single_day):
    """
    Create a 24-hour timeline visualization with sleep/awake periods and activity markers.
    
    Args:
        df_single_day: DataFrame with columns ['datetime', 'Action'] sorted by datetime
        
    Returns:
        plotly Figure object
    """
    # Sort by datetime for timeline
    df_timeline = df_single_day.sort_values(by='datetime', ascending=True).copy()
    
    # Create figure
    fig = go.Figure()
    
    # Process sleep periods (Gantt chart bars)
    sleep_periods = []
    awake_periods = []
    current_sleep_start = None
    previous_time = None
    
    for idx, row in df_timeline.iterrows():
        if row['Action'].lower() == 'slept':
            # If there was a previous woke up time, this is an awake period
            if previous_time is not None:
                awake_periods.append({
                    'start': previous_time,
                    'end': row['datetime']
                })
            current_sleep_start = row['datetime']
            previous_time = None
        elif row['Action'].lower() == 'woke up' and current_sleep_start is not None:
            sleep_periods.append({
                'start': current_sleep_start,
                'end': row['datetime']
            })
            previous_time = row['datetime']
            current_sleep_start = None
    
    # Add awake periods (Matrix green)
    for i, period in enumerate(awake_periods):
        start_time = period['start'].hour + period['start'].minute/60 + period['start'].second/3600
        end_time = period['end'].hour + period['end'].minute/60 + period['end'].second/3600
        duration = end_time - start_time
        
        fig.add_trace(go.Bar(
            x=[duration],
            y=['Timeline'],
            base=start_time,
            orientation='h',
            marker=dict(color='rgba(0, 255, 65, 0.3)', line=dict(color='rgba(0, 255, 65, 0.8)', width=1)),
            name='Awake' if i == 0 else '',
            showlegend=(i == 0),
            hovertemplate=f"Awake: {period['start'].strftime('%I:%M %p')} - {period['end'].strftime('%I:%M %p')}<br>Duration: {int(duration)}h {int((duration % 1) * 60)}m<extra></extra>"
        ))
    
    # Add sleep periods (Matrix dark with neon outline)
    for i, period in enumerate(sleep_periods):
        start_time = period['start'].hour + period['start'].minute/60 + period['start'].second/3600
        end_time = period['end'].hour + period['end'].minute/60 + period['end'].second/3600
        duration = end_time - start_time
        
        fig.add_trace(go.Bar(
            x=[duration],
            y=['Timeline'],
            base=start_time,
            orientation='h',
            marker=dict(color='rgba(0, 20, 40, 0.8)', line=dict(color='rgba(0, 255, 255, 0.6)', width=2)),
            name='Sleep' if i == 0 else '',
            showlegend=(i == 0),
            hovertemplate=f"Sleep: {period['start'].strftime('%I:%M %p')} - {period['end'].strftime('%I:%M %p')}<br>Duration: {int(duration)}h {int((duration % 1) * 60)}m<extra></extra>"
        ))
    
    # Add other activities as markers positioned in middle of timeline bar
    other_activities = df_timeline[~df_timeline['Action'].str.lower().isin(['slept', 'woke up'])].copy()
    
    # Matrix-themed color mapping for different activities
    activity_colors = {
        'Fed': '#00FF41',  # Matrix green
        'Solid Food': '#FF6EC7',  # Neon pink
        'Diaper Change': '#FFD700',  # Gold
        'Potty': '#00FFFF',  # Cyan
        'Water': '#8A2BE2'  # Blue violet
    }
    
    if not other_activities.empty:
        for activity_type in other_activities['Action'].unique():
            activity_data = other_activities[other_activities['Action'] == activity_type]
            times = activity_data['datetime'].dt.hour + activity_data['datetime'].dt.minute/60 + activity_data['datetime'].dt.second/3600
            
            fig.add_trace(go.Scatter(
                x=times.tolist(),
                y=['Timeline'] * len(times),
                mode='markers+text',
                marker=dict(
                    size=18,
                    color=activity_colors.get(activity_type, '#FFFFFF'),
                    symbol='circle',
                    line=dict(width=3, color='rgba(0, 0, 0, 0.8)')
                ),
                text=['●'] * len(times),
                textposition='middle center',
                textfont=dict(size=20, color=activity_colors.get(activity_type, '#FFFFFF')),
                name=activity_type,
                hovertext=[f"{activity_type}<br>{dt.strftime('%I:%M %p')}" for dt in activity_data['datetime']],
                hovertemplate='%{hovertext}<extra></extra>'
            ))
    
    # Update layout with Matrix theme
    fig.update_layout(
        title=dict(
            text=f"24-Hour Timeline",
            font=dict(color='#00FF41', size=20)
        ),
        paper_bgcolor='rgba(0, 10, 20, 1)',
        plot_bgcolor='rgba(0, 0, 0, 0.9)',
        xaxis=dict(
            title=dict(text="Time of Day", font=dict(color='#00FF41')),
            tickmode='array',
            range=[0, 24],
            tickvals=[0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24],
            ticktext=['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00', '24:00'],
            showgrid=True,
            gridcolor='rgba(0, 255, 65, 0.2)',
            tickfont=dict(color='#00FF41')
        ),
        yaxis=dict(
            title="",
            showticklabels=False,
            showgrid=False
        ),
        height=250,
        hovermode='closest',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='#00FF41'),
            bgcolor='rgba(0, 0, 0, 0.7)'
        ),
        barmode='overlay',
        bargap=0
    )
    
    return fig
