"""Pure chart construction. Reference guides are never measurement rows."""
import altair as alt
import pandas as pd


def reference_data(frame, x, y):
    usable = frame[frame[x].gt(0) & frame[y].gt(0)].copy()
    if usable.empty:
        return pd.DataFrame(columns=[x,y,'guide'])
    start = usable[x].min()
    anchor = usable.loc[usable[x].eq(start),y].median()
    rows = []
    for name,power in [('linear (slope 1)',1),('quadratic (slope 2)',2)]:
        for n in sorted(usable[x].unique()):
            rows.append({x:n,y:anchor*(n/start)**power,'guide':name})
    return pd.DataFrame(rows)


def line_plot(frame, x, y, xlabel, ylabel, series='version', logx=False, logy=False, references=False):
    xaxis = alt.X(f'{x}:Q',title=xlabel,scale=alt.Scale(type='log' if logx else 'linear'))
    yaxis = alt.Y(f'{y}:Q',title=ylabel,scale=alt.Scale(type='log' if logy else 'linear'))
    tips = [alt.Tooltip(f'{x}:Q',title=xlabel),alt.Tooltip(f'{y}:Q',title=ylabel)]
    tips += [c for c in (series,'seed','workload','run','commit') if c in frame and c not in (x,y)]
    enc = dict(x=xaxis,y=yaxis,color=alt.Color(f'{series}:N'),tooltip=tips)
    if 'seed' in frame: enc['detail'] = alt.Detail('seed:N')
    actual = alt.Chart(frame).mark_line(point=True).encode(**enc)
    if references and logx and logy and frame[x].nunique() >= 2:
        guides = alt.Chart(reference_data(frame,x,y)).mark_line(color='#777777').encode(
            x=xaxis,y=yaxis,detail='guide:N',
            strokeDash=alt.StrokeDash('guide:N',title='Reference only',scale=alt.Scale(
                domain=['linear (slope 1)','quadratic (slope 2)'],range=[[6,4],[2,4]])),
            tooltip=['guide',alt.Tooltip(f'{x}:Q',title=xlabel),alt.Tooltip(f'{y}:Q',title=ylabel)])
        return (actual+guides).properties(height=310).interactive()
    return actual.properties(height=310).interactive()
