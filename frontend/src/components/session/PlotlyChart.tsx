import React, { useMemo, useRef, useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
// @ts-ignore
import Plotly from 'plotly.js-dist-min';
import { CopyRegular, CheckmarkRegular } from '@fluentui/react-icons';


import { PlotlyFigureSpec } from '../../types';

interface PlotlyChartProps {
  figure: PlotlyFigureSpec;
  className?: string;
}

export const PlotlyChart: React.FC<PlotlyChartProps> = React.memo(({ figure, className = '' }) => {
  const plotDivRef = useRef<any>(null);
  const [copied, setCopied] = useState(false);

  const isMultiPlot = useMemo(() => {
    const origLayout = figure.layout || {};
    return Boolean(
      origLayout.grid ||
      origLayout.xaxis2 ||
      origLayout.yaxis2 ||
      figure.data?.some((t: any) => t.xaxis?.includes('2') || t.xaxis?.includes('3') || t.xaxis?.includes('4'))
    );
  }, [figure.layout, figure.data]);

  const mergedLayout = useMemo(() => {
    const origLayout = figure.layout || {};

    // 1. Resolve / guarantee Plot Title
    let titleText = '';
    if (typeof origLayout.title === 'string') {
      titleText = origLayout.title.trim();
    } else if (origLayout.title && typeof origLayout.title.text === 'string') {
      titleText = origLayout.title.text.trim();
    }

    if (!titleText) {
      const firstTrace = figure.data?.[0];
      if (firstTrace?.name && firstTrace.name !== 'trace 0') {
        titleText = `${firstTrace.name} Analysis Plot`;
      } else if (firstTrace?.type === 'histogram') {
        titleText = 'Distribution & Histogram Plot';
      } else if (firstTrace?.type === 'box') {
        titleText = 'Boxplot Analysis';
      } else if (firstTrace?.type === 'scatter') {
        titleText = 'Scatter & Regression Plot';
      } else if (firstTrace?.type === 'surface' || firstTrace?.type === 'contour') {
        titleText = 'Response Surface / Contour Plot';
      } else {
        titleText = 'Statistical Analysis Plot';
      }
    }

    const enhancedLayout: Record<string, any> = {
      autosize: true,
      paper_bgcolor: '#ffffff',
      plot_bgcolor: '#ffffff',
      font: {
        family: 'Segoe UI, Inter, -apple-system, BlinkMacSystemFont, sans-serif',
        size: 11.5,
        color: '#1f2937',
      },
      ...origLayout,
      title: {
        text: titleText,
        font: {
          family: 'Segoe UI, Inter, -apple-system, BlinkMacSystemFont, sans-serif',
          size: 14,
          color: '#111827',
          weight: 600,
        },
        x: 0.5,
        xanchor: 'center',
        y: 0.98,
        yanchor: 'top',
        ...(typeof origLayout.title === 'object' ? origLayout.title : {}),
      },
    };
    enhancedLayout.title.text = titleText;
    // Remove built-in template string (e.g. plotly_white) so it cannot strip our 4-sided bounding frame
    delete enhancedLayout.template;

    // 2. Compute explicit non-overlapping domains if multi-panel grid layout
    if (origLayout.grid) {
      const cols = origLayout.grid.columns || 2;
      const rows = origLayout.grid.rows || 2;
      const xGutter = 0.22; // 22% clear buffer zone between subplot columns
      const yGutter = 0.22; // 22% clear buffer zone between subplot rows
      const colWidth = (1.0 - (cols - 1) * xGutter) / cols;
      const rowHeight = (1.0 - (rows - 1) * yGutter) / rows;

      let axisIdx = 1;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const xKey = axisIdx === 1 ? 'xaxis' : `xaxis${axisIdx}`;
          const yKey = axisIdx === 1 ? 'yaxis' : `yaxis${axisIdx}`;

          const x0 = c * (colWidth + xGutter);
          const x1 = x0 + colWidth;
          const y1 = 1.0 - r * (rowHeight + yGutter);
          const y0 = y1 - rowHeight;

          enhancedLayout[xKey] = {
            domain: [Math.max(0, parseFloat(x0.toFixed(4))), Math.min(1, parseFloat(x1.toFixed(4)))],
            ...(enhancedLayout[xKey] || {}),
          };
          enhancedLayout[yKey] = {
            domain: [Math.max(0, parseFloat(y0.toFixed(4))), Math.min(1, parseFloat(y1.toFixed(4)))],
            ...(enhancedLayout[yKey] || {}),
          };

          axisIdx++;
        }
      }
      delete enhancedLayout.grid;
    }

    // 3. Configure 4-sided bounding frame, inside ticks, gridlines, and anchors across all active axes
    const activeAxesList: number[] = [];
    for (let i = 1; i <= 16; i++) {
      const xKey = i === 1 ? 'xaxis' : `xaxis${i}`;
      const yKey = i === 1 ? 'yaxis' : `yaxis${i}`;

      const existingX = origLayout[xKey] || enhancedLayout[xKey];
      const existingY = origLayout[yKey] || enhancedLayout[yKey];

      const isReferenced = Boolean(
        existingX ||
        existingY ||
        i === 1 ||
        (origLayout.grid && i <= (origLayout.grid.rows || 1) * (origLayout.grid.columns || 1)) ||
        figure.data?.some((t: any) =>
          t.xaxis === (i === 1 ? 'x' : `x${i}`) ||
          t.xaxis === `x${i}` ||
          t.yaxis === (i === 1 ? 'y' : `y${i}`) ||
          t.yaxis === `y${i}`
        )
      );

      if (isReferenced) {
        activeAxesList.push(i);
        const curX = existingX || {};
        let xTitle = '';
        if (typeof curX.title === 'string') {
          xTitle = curX.title.trim();
        } else if (curX.title && typeof curX.title.text === 'string') {
          xTitle = curX.title.text.trim();
        }

        // Default single-plot x title only if not a multiplot
        if (!xTitle && !isMultiPlot && i === 1) {
          const firstTrace = figure.data?.[0];
          if (firstTrace?.type === 'histogram') {
            xTitle = 'Values / Intervals';
          } else if (firstTrace?.type === 'box') {
            xTitle = 'Sample Groups';
          } else if (firstTrace?.mode?.includes('lines') || firstTrace?.type === 'scatter') {
            xTitle = 'Sample / Subgroup Index';
          } else {
            xTitle = 'X Variable';
          }
        }

        enhancedLayout[xKey] = {
          ...curX,
          anchor: curX.anchor || (i === 1 ? 'y' : `y${i}`),
          automargin: true,
          showgrid: true,
          gridcolor: '#ececec',
          gridwidth: 1,
          showline: true,
          mirror:
            curX.mirror !== undefined
              ? curX.mirror
              : curX.domain && curX.domain[0] > 0 && curX.domain[1] < 1
              ? 'ticks'
              : true, // Top and bottom bounding lines without duplicate side borders
          linecolor: '#201f1e',
          linewidth: 1.25,
          zeroline: false,
          ticks: 'inside',
          tickcolor: '#201f1e',
          ticklen: 4,
          tickwidth: 1.25,
          tickfont: {
            family: 'Segoe UI, Inter, -apple-system, BlinkMacSystemFont, sans-serif',
            size: 11,
            color: '#201f1e',
          },
        };


        if (xTitle) {
          enhancedLayout[xKey].title = {
            text: xTitle,
            font: {
              family: 'Segoe UI, Inter, -apple-system, BlinkMacSystemFont, sans-serif',
              size: 11.5,
              color: '#374151',
              weight: 500,
            },
            ...(typeof curX.title === 'object' ? curX.title : {}),
          };
          enhancedLayout[xKey].title.text = xTitle;
        }

        const curY = existingY || {};
        let yTitle = '';
        if (typeof curY.title === 'string') {
          yTitle = curY.title.trim();
        } else if (curY.title && typeof curY.title.text === 'string') {
          yTitle = curY.title.text.trim();
        }

        // Default single-plot y title only if not a multiplot
        if (!yTitle && !isMultiPlot && i === 1) {
          const firstTrace = figure.data?.[0];
          if (firstTrace?.type === 'histogram') {
            yTitle = 'Frequency / Count';
          } else if (firstTrace?.type === 'box') {
            yTitle = 'Observed Measurements';
          } else {
            yTitle = 'Response / Value';
          }
        }

        enhancedLayout[yKey] = {
          ...curY,
          anchor: curY.anchor || (i === 1 ? 'x' : `x${i}`),
          automargin: true,
          showgrid: true,
          gridcolor: '#ececec',
          gridwidth: 1,
          showline: true,
          mirror: true, // Left and right bounding lines
          linecolor: '#201f1e',
          linewidth: 1.25,
          zeroline: false,
          ticks: 'inside',
          tickcolor: '#201f1e',
          ticklen: 4,
          tickwidth: 1.25,
          tickfont: {
            family: 'Segoe UI, Inter, -apple-system, BlinkMacSystemFont, sans-serif',
            size: 11,
            color: '#201f1e',
          },
        };

        if (yTitle) {
          enhancedLayout[yKey].title = {
            text: yTitle,
            font: {
              family: 'Segoe UI, Inter, -apple-system, BlinkMacSystemFont, sans-serif',
              size: 11.5,
              color: '#374151',
              weight: 500,
            },
            ...(typeof curY.title === 'object' ? curY.title : {}),
          };
          enhancedLayout[yKey].title.text = yTitle;
        }
      }
    }




    const hasBottomLegend =
      enhancedLayout.legend &&
      (enhancedLayout.legend.orientation === 'h' ||
        (typeof enhancedLayout.legend.y === 'number' && enhancedLayout.legend.y <= 0));

    const origMargin = origLayout.margin || {};
    const minLeft = Math.max(isMultiPlot ? 65 : 75, origMargin.l || 65);
    const minRight = Math.max(isMultiPlot ? 45 : 55, origMargin.r || 45);
    const minTop = Math.max(isMultiPlot ? 65 : 70, origMargin.t || 65);
    const minBottom = Math.max(hasBottomLegend ? 90 : 60, origMargin.b || 60);

    enhancedLayout.margin = {
      l: minLeft,
      r: minRight,
      t: minTop,
      b: minBottom,
      pad: 4,
      ...origMargin,
    };

    return enhancedLayout;
  }, [figure.layout, figure.data, isMultiPlot]);

  const config = useMemo(() => {
    return {
      responsive: true,
      displaylogo: false,
      displayModeBar: 'hover' as const,
      modeBarButtonsToRemove: ['lasso2d', 'select2d'] as any,
      toImageButtonOptions: {
        format: 'png' as const,
        filename: 'libretab_chart',
        height: 700,
        width: 1000,
        scale: 2,
      },
      ...figure.config,
    };
  }, [figure.config]);

  const heightVal = useMemo(() => {
    if (figure.layout?.height) return figure.layout.height;
    const rows = figure.layout?.grid?.rows;
    if (rows && rows >= 2) return 640;
    if (isMultiPlot) return 620;
    return 420;
  }, [figure.layout?.height, figure.layout?.grid?.rows, isMultiPlot]);

  // Ensure window.Plotly is accessible for project IO and global print triggers
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).Plotly = Plotly;
    }
  }, []);

  // Dynamically resize Plotly SVG keeping exact aspect ratio to fit the PDF printable width
  useEffect(() => {
    const handleBeforePrint = async () => {
      if (plotDivRef.current) {
        try {
          const curW = plotDivRef.current.clientWidth || plotDivRef.current.getBoundingClientRect().width || 900;
          const curH = plotDivRef.current.clientHeight || plotDivRef.current.getBoundingClientRect().height || heightVal;
          const aspectRatio = curH / Math.max(curW, 100);

          const cardEl = plotDivRef.current.closest('.plotly-chart-card');
          const printableWidth = cardEl && cardEl.clientWidth > 400 ? cardEl.clientWidth - 16 : 700;
          const printableHeight = Math.round(printableWidth * aspectRatio);

          await Plotly.relayout(plotDivRef.current, {
            width: printableWidth,
            height: printableHeight,
            autosize: false,
          });
        } catch (_) {}
      }
    };

    const handleAfterPrint = async () => {
      if (plotDivRef.current) {
        try {
          await Plotly.relayout(plotDivRef.current, {
            width: null,
            height: heightVal,
            autosize: true,
          });
        } catch (_) {}
      }
    };

    window.addEventListener('beforeprint', handleBeforePrint);
    window.addEventListener('afterprint', handleAfterPrint);
    return () => {
      window.removeEventListener('beforeprint', handleBeforePrint);
      window.removeEventListener('afterprint', handleAfterPrint);
    };
  }, [heightVal, isMultiPlot]);




  const handleCopyChartImage = async () => {
    if (!plotDivRef.current) return;
    try {
      const url = await Plotly.toImage(plotDivRef.current, {
        format: 'png',
        width: 1200,
        height: 800,
        scale: 2,
      });

      const res = await fetch(url);
      const blob = await res.blob();

      await navigator.clipboard.write([
        new ClipboardItem({
          'image/png': blob,
        }),
      ]);

      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch (err) {
      console.error('Failed to copy plot image to clipboard:', err);
    }
  };


  return (
    <div className={`plotly-chart-card relative group w-full max-w-5xl mx-auto bg-white rounded border border-[#e5e7eb] p-2.5 shadow-none transition-all ${className}`}>
      {/* 1-Click Copy Chart Image Button */}
      <button
        type="button"
        onClick={handleCopyChartImage}
        className="print:hidden absolute top-3 right-3 z-20 flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded bg-white/90 hover:bg-[#008450] hover:text-white text-[#323130] border border-[#d2d0ce] shadow-xs backdrop-blur-xs opacity-0 group-hover:opacity-100 transition-all cursor-pointer"
        title="Copy High-Res PNG Chart Image to Clipboard (Ctrl+V into Word / PowerPoint)"
      >


        {copied ? (
          <>
            <CheckmarkRegular className="w-3.5 h-3.5 text-emerald-600 group-hover:text-white" />
            <span className="text-emerald-700 group-hover:text-white">Copied PNG</span>
          </>
        ) : (
          <>
            <CopyRegular className="w-3.5 h-3.5" />
            <span>Copy Image</span>
          </>
        )}
      </button>

      <Plot
        data={figure.data}
        layout={mergedLayout as any}
        config={config as any}
        style={{ width: '100%', height: `${heightVal}px`, minHeight: '350px' }}
        useResizeHandler={true}
        className="w-full h-full"
        onInitialized={(_, graphDiv) => {
          plotDivRef.current = graphDiv;
        }}
      />
    </div>
  );
});

PlotlyChart.displayName = 'PlotlyChart';
