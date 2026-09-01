# How to Use LibRE Sigma

This user guide walks you through the core workflow of **LibRE Sigma**: managing multi-sheet workbooks, importing data, running statistical analyses, inspecting interactive charts, and exporting results.

---

## 1. Workspace Layout

The LibRE Sigma user interface is structured into five primary functional regions:

```
+-------------------------------------------------------------------------+
| Top Menu & Ribbon Toolbar (File, Edit, Data, Calc, Stat, Graph, Help)    |
+-------------------+-----------------------------------------------------+
|                   | Upper Pane: Session Output Transcript & Plotly View |
| Left Navigator    | (Statistical results, ANOVA tables, charts)         |
| Sidebar           +-----------------------------------------------------+
| (Worksheets &     | Resizable Divider Bar                               |
| Session history)  +-----------------------------------------------------+
|                   | Lower Pane: Dynamic Formula Bar & Worksheet Grid    |
|                   | (Multi-sheet tabs: Sheet 1, Sheet 2, ...)           |
+-------------------+-----------------------------------------------------+
| Status Bar (Active sheet name, row/column counts, selection metrics)    |
+-------------------------------------------------------------------------+
```

1. **Top Menu & Ribbon**: Quick access to statistical procedures, DOE creation wizards, file management, and data manipulation tools.
2. **Left Navigator**: Tree explorer displaying active sheets, DOE matrices, and history of statistical output sessions.
3. **Session Output Pane**: Dedicated transcript area displaying Markdown text summaries, structured statistical tables, $p$-values, test statistics, and interactive Plotly figures.
4. **Formula Bar & Worksheet Grid**: High-performance dual-header spreadsheet with dynamic $C_1, C_2, \dots, C_n$ column indices, named variables, data types (Numeric, Text, Date), and formula evaluation.
5. **Status Bar**: Real-time summary information, active worksheet dimensions, and computed statistics for the active selection.

---

## 2. Importing & Managing Data

### Open / Import Files

LibRE Sigma supports native project files, Excel spreadsheets, and delimited text:

- **Native Project (`.lsg`, `.ltb`)**: `Ctrl+O` or `File > Open Project / Data`. Restores complete project state, multiple sheets, column metadata, and session history.
- **Excel (`.xlsx`, `.xls`)**: `Ctrl+I` or `File > Import Excel Workbook`. Automatically imports all sheets in the workbook.
- **CSV / TSV / TXT**: `File > Import CSV / Text Data` or drag and drop any `.csv` file onto the application window.

::: tip Sample Datasets Included
You can quickly explore the application by navigating to **Help > Open Sample Dataset**, which provides standard benchmark datasets for Gage R&R, Weibull life testing, and Taguchi optimization.
:::

### Manual Data Entry & Formulas

- **Dual-Header Editing**: Double-click any column header to rename the variable. Type indicator labels (`-T` for Text, `-D` for Date) update automatically based on entered data.
- **Formula Execution**: Select a target column, click the **Formula Bar**, and enter expressions like `C1 * 1.5`, `LN(C2)`, `STANDARDIZE(C3)`, or `C2 - C1`. Formulas evaluate automatically across all rows.
- **Patterned Data Generation**: Navigate to `Data > Create Patterned Data` to populate numeric sequences (e.g. `1 to 50 by 2`) or categorical factor levels (`A, B, C` repeated $N$ times).

### Data Manipulation Tools

- **Sort Columns**: `Data > Sort Columns` allows multi-key sorting with ascending/descending criteria.
- **Stack / Unstack**: `Data > Stack Columns` reshapes wide columns into tall subscripted pairs; `Data > Unstack Columns` reverses the transformation.
- **Recode**: `Data > Recode Data` maps categorical text or bins numeric continuous ranges into new discrete categories.
- **Subset Worksheet**: `Data > Subset Worksheet` filters rows based on conditional expressions (e.g. `Batch == "A" & Temperature > 80`) into a new sheet.

---

## 3. Running a Statistical Analysis

To perform any statistical test or quality calculation:

1. **Select Procedure**: Click the desired menu item (e.g., `Stat > Basic Statistics > 2-Sample t-Test` or `Stat > Control Charts > Variables Charts for Subgroups > Xbar-R`).
2. **Configure Parameters Modal**:
   - Double-click columns in the left column picker list to insert them into active variable fields.
   - Adjust options such as **Confidence Level**, **Hypothesized Difference**, or **Alternative Hypothesis**.
3. **Execute**: Click **OK** (`Enter`) to dispatch computation to the local Python engine.
4. **View Results**:
   - The **Session Output** pane immediately displays formatted statistical tables, $p$-values, confidence intervals, and interactive Plotly figures.
   - Click and drag on any chart to zoom, double-click to reset view, and hover over data points to inspect Nelson rule alarms or subgroup statistics.

---

## 4. Keyboard Shortcuts

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| `Ctrl+N` | New Project | Clears current session and starts fresh workbook |
| `Ctrl+O` | Open Project | Opens `.lsg` project or dataset |
| `Ctrl+S` | Save Project | Saves project with all sheets and output history |
| `Ctrl+Shift+S` | Save Project As | Saves project under a new filename |
| `Ctrl+I` | Import Excel | Imports `.xlsx` multi-sheet workbook |
| `Ctrl+Z` | Undo | Reverts last grid or worksheet operation |
| `Ctrl+Y` / `Ctrl+Shift+Z` | Redo | Re-applies undone operation |
| `Ctrl+C` | Copy | Copies selected cells to clipboard |
| `Ctrl+V` | Paste | Pastes clipboard content into grid |
| `F1` | Documentation | Opens the online/offline documentation site |
