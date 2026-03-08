---
name: pipeline-marimo
description: Marimo reactive notebook construction and best practices. Use when creating interactive analysis notebooks, exploratory data analysis, parameter exploration, or the user mentions marimo, notebooks, or interactive analysis.
---

# Marimo Notebooks

## When To Use

- Exploratory data analysis and visualization
- Interactive parameter exploration
- Prototyping analysis steps before encoding in Snakemake
- Presenting results with interactivity
- Quick one-off analyses that don't need pipeline formalization

For production pipelines with file dependencies, prefer Snakemake.

## Project Structure

```
code/notebooks/
├── viz.py              # Knowledge graph visualization (auto-generated)
├── explore-data.py     # Data exploration notebook
├── analyze-results.py  # Results analysis
└── parameter-sweep.py  # Interactive parameter testing
```

## Creating a Notebook

```bash
# Create and open a new notebook
uv run marimo edit code/notebooks/explore-data.py

# Run as a read-only app
uv run marimo run code/notebooks/explore-data.py
```

## Notebook Structure

### Standard sections

Organize notebooks with clear cell progression:

1. **Setup** — imports, configuration, data paths
2. **Data loading** — read from `data/raw/` or `data/processed/`
3. **Processing** — transformations, filtering, normalization
4. **Visualization** — charts, tables, summary statistics
5. **Export** — save results to `data/processed/` with provenance

### Example notebook

```python
import marimo

app = marimo.App(width="medium")


@app.cell
def setup():
    import marimo as mo
    import polars as pl
    import altair as alt
    return mo, pl, alt


@app.cell
def load_data(pl):
    data = pl.read_csv("../../data/processed/normalized.csv")
    data.head()
    return (data,)


@app.cell
def explore(mo, data):
    # Interactive column selector
    column = mo.ui.dropdown(
        options=data.columns,
        value=data.columns[0],
        label="Select column",
    )
    column
    return (column,)


@app.cell
def visualize(data, alt, column):
    chart = alt.Chart(data.to_pandas()).mark_bar().encode(
        x=alt.X(column.value, bin=True),
        y="count()",
    ).properties(width=600, height=400)
    chart
    return (chart,)


@app.cell
def export(data):
    # Export filtered/processed results
    output_path = "../../data/processed/explored_subset.csv"
    data.write_csv(output_path)
    print(f"Exported to {output_path}")
    return ()
```

## Best Practices

### Data access
- Use relative paths from notebook location: `../../data/raw/`
- Load data with polars (preferred) or pandas
- For large datasets, use lazy evaluation: `pl.scan_csv()`

### Interactive elements
- `mo.ui.slider()` — numeric parameter exploration
- `mo.ui.dropdown()` — categorical selection
- `mo.ui.checkbox()` — toggle options
- `mo.ui.text()` — free-form input
- `mo.ui.table()` — interactive data tables

### Visualization
- Prefer Altair for declarative charts (integrates well with marimo)
- Use `mo.ui.altair_chart()` for interactive selection
- For specialized plots, seaborn is acceptable

### Reactivity
- Marimo cells are reactive: changing a cell re-runs dependents
- Name return values explicitly to create dependencies
- Avoid side effects in cells (file writes should be in dedicated export cells)

### Connecting to Science workflow
- Read inquiry variables from graph: `science-tool inquiry show <slug> --format json`
- Load `datapackage.json` to understand available fields
- Export results with provenance metadata
- Document findings in `doc/` after exploration
