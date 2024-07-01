import altair as alt

def create_altair_labelled_vertical_bar_chart(df, x_field, x_label, y_field, y_label):
    """
    creates a vertical bar chart with labels at the end of the bars
    """
    
    base = alt.Chart(df).encode(
        x=alt.X(
            x_field, 
            title=x_label, 
            axis=alt.Axis(format="0,.0f", ticks=False, domain=False)
            ),
        y=alt.Y(y_field, title=y_label, axis=alt.Axis(labelFontSize=14, titleFontSize=18)),
        text=alt.Text(x_field, format="0,.0f"),
    )

    return (
        base.mark_bar()
        + base.mark_text(align='right', size=18, color='#FFFFFF', dx=-5)
        )