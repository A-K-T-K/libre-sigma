import React from 'react';
import {
  // Time Series & Forecasting
  TrendingUp,
  LineChart,
  CandlestickChart,
  Layers,
  CircleDot,
  Activity,
  ArrowRightLeft,
  ArrowRight,
  BarChart2,
  BarChart3,
  Sliders,
  AreaChart,
  // Basic Statistics & Hypothesis Tests
  FileSpreadsheet,
  FileBarChart,
  Calculator,
  Bell,
  GitCompare,
  Columns,
  Percent,
  Scan,
  Target,
  Network,
  // Regression & ANOVA
  FunctionSquare,
  Sigma,
  Filter,
  ListChecks,
  BarChart,
  Split,
  GitFork,
  // Nonparametrics & Tables
  ScatterChart,
  ArrowUpDown,
  Table,
  Grid,
  // DOE & Optimization
  Box,
  Grid3X3,
  Mountain,
  Triangle,
  LayoutGrid,
  SlidersHorizontal,
  // Quality Tools & SPC Control Charts
  ShieldCheck,
  Gauge,
  Ruler,
  GitBranch,
  Workflow,
  // Reliability & Survival
  Hourglass,
  Clock,
  Wrench,
  RefreshCw,
  // Multivariate & General
  Boxes,
  PieChart,
  HelpCircle,
  FolderOpen,
  FilePlus,
  Upload,
  Download,
  Undo2,
  Redo2,
  Eraser,
  Trash2,
  Copy,
  Scissors,
  ClipboardPaste,
  PlusSquare,
  ArrowUpDown as SortIcon,
  Info,
  Save,
  Printer,
} from 'lucide-react';



export const getMenuOrPluginIcon = (id: string, pluginId?: string): React.ReactNode => {
  const targetId = pluginId || id;

  // 1. Time Series & Forecasting
  switch (targetId) {
    case 'ts_plot':
      return <LineChart className="w-3.5 h-3.5 text-emerald-600" />;
    case 'ts_trend_analysis':
      return <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />;
    case 'ts_decomposition':
      return <Layers className="w-3.5 h-3.5 text-emerald-700" />;
    case 'ts_moving_average':
      return <CircleDot className="w-3.5 h-3.5 text-teal-600" />;
    case 'ts_single_exp_smoothing':
    case 'ts_double_exp_smoothing':
    case 'ts_winters_method':
      return <Activity className="w-3.5 h-3.5 text-emerald-600" />;
    case 'ts_differences':
      return <ArrowRightLeft className="w-3.5 h-3.5 text-teal-700" />;
    case 'ts_lag':
      return <ArrowRight className="w-3.5 h-3.5 text-teal-700" />;
    case 'ts_autocorrelation':
    case 'ts_partial_autocorrelation':
    case 'ts_cross_correlation':
      return <BarChart2 className="w-3.5 h-3.5 text-emerald-600" />;
    case 'ts_box_cox':
      return <Sliders className="w-3.5 h-3.5 text-teal-600" />;
    case 'ts_adf_test':
      return <Activity className="w-3.5 h-3.5 text-rose-600" />;
    case 'ts_arima':
    case 'ts_auto_arima':
      return <AreaChart className="w-3.5 h-3.5 text-emerald-700" />;

    // 2. Basic Statistics & Hypothesis Tests
    case 'display_descriptives':
      return <FileBarChart className="w-3.5 h-3.5 text-blue-600" />;
    case 'store_descriptives':
      return <FileSpreadsheet className="w-3.5 h-3.5 text-blue-600" />;
    case 'graphical_summary':
      return <AreaChart className="w-3.5 h-3.5 text-blue-600" />;
    case 'one_sample_z':
    case 'one_sample_t':
    case 'paired_t':
    case 'one_variance':
      return <Bell className="w-3.5 h-3.5 text-blue-700" />;
    case 'two_sample_t':
    case 'two_variances':
      return <GitCompare className="w-3.5 h-3.5 text-blue-600" />;
    case 'one_proportion':
    case 'two_proportions':
      return <Percent className="w-3.5 h-3.5 text-blue-600" />;
    case 'one_sample_poisson_rate':
    case 'two_sample_poisson_rate':
    case 'goodness_of_fit_poisson':
      return <BarChart3 className="w-3.5 h-3.5 text-blue-600" />;
    case 'normality_test':
      return <AreaChart className="w-3.5 h-3.5 text-indigo-600" />;
    case 'outlier_test':
      return <Scan className="w-3.5 h-3.5 text-rose-600" />;
    case 'correlation':
    case 'covariance':
      return <Network className="w-3.5 h-3.5 text-blue-600" />;

    // 3. Regression & ANOVA
    case 'fitted_line_plot':
    case 'binary_fitted_line_plot':
      return <LineChart className="w-3.5 h-3.5 text-indigo-600" />;
    case 'general_regression':
    case 'logistic_regression':
    case 'poisson_regression':
    case 'nonlinear_regression':
    case 'orthogonal_regression':
    case 'partial_least_squares':
    case 'stability_study':
      return <FunctionSquare className="w-3.5 h-3.5 text-indigo-700" />;
    case 'regression_stepwise':
      return <Filter className="w-3.5 h-3.5 text-indigo-600" />;
    case 'one_way_anova':
    case 'balanced_anova':
    case 'general_linear_model':
    case 'mixed_effects_model':
    case 'general_manova':
    case 'fully_nested_anova':
    case 'test_equal_variances':
      return <BarChart className="w-3.5 h-3.5 text-violet-600" />;
    case 'interaction_plot':
    case 'main_effects_plot':
    case 'interval_plot':
    case 'anom':
      return <Split className="w-3.5 h-3.5 text-violet-600" />;

    // 4. Nonparametrics & Tables
    case 'nonparam_1sample_wilcoxon':
    case 'nonparam_mann_whitney':
    case 'nonparam_kruskal_wallis':
    case 'nonparam_moods_median':
    case 'nonparam_friedman':
      return <ScatterChart className="w-3.5 h-3.5 text-amber-600" />;
    case 'tables_cross_tabulation':
    case 'tables_chisq_gof':
      return <Table className="w-3.5 h-3.5 text-amber-700" />;

    // 5. Design of Experiments (DOE) & Optimization
    case 'doe_create_factorial':
    case 'doe_analyze_factorial':
      return <Box className="w-3.5 h-3.5 text-cyan-600" />;
    case 'doe_create_rsm':
    case 'doe_analyze_rsm':
      return <Mountain className="w-3.5 h-3.5 text-cyan-700" />;
    case 'doe_create_mixture':
    case 'doe_analyze_mixture':
      return <Triangle className="w-3.5 h-3.5 text-cyan-600" />;
    case 'doe_create_taguchi':
    case 'doe_analyze_taguchi':
      return <LayoutGrid className="w-3.5 h-3.5 text-cyan-700" />;
    case 'doe_response_optimizer':
      return <SlidersHorizontal className="w-3.5 h-3.5 text-teal-600" />;

    // 6. Power and Sample Size
    case 'power_and_sample_size':
      return <Target className="w-3.5 h-3.5 text-blue-600" />;

    // 7. Quality Tools & SPC Control Charts
    case 'process_capability':
    case 'capability_nonnormal':
      return <ShieldCheck className="w-3.5 h-3.5 text-sky-600" />;
    case 'capability_sixpack':
      return <Gauge className="w-3.5 h-3.5 text-sky-600" />;
    case 'gage_rr':
    case 'gage_rr_nested':
    case 'gage_linearity_bias':
    case 'attribute_agreement':
    case 'acceptance_sampling':
      return <Ruler className="w-3.5 h-3.5 text-sky-700" />;
    case 'pareto_chart':
      return <BarChart3 className="w-3.5 h-3.5 text-sky-600" />;
    case 'run_chart':
    case 'multi_vari':
    case 'symmetry_plot':
    case 'tolerance_intervals':
    case 'cause_and_effect':
    case 'distribution_id':
    case 'johnson_transformation':
      return <Activity className="w-3.5 h-3.5 text-sky-600" />;
    case 'xbar_r':
    case 'xbar_s':
    case 'xbar_only':
    case 'r_chart':
    case 's_chart':
    case 'zone_chart':
    case 'i_mr':
    case 'individual_only':
    case 'mr_only':
    case 'z_mr':
    case 'p_chart':
    case 'np_chart':
    case 'c_chart':
    case 'u_chart':
    case 'laney_p_prime':
    case 'laney_u_prime':
    case 'g_chart':
    case 't_chart':
    case 't2_multivariate':
    case 'generalized_variance':
      return <Workflow className="w-3.5 h-3.5 text-teal-600" />;
    case 'cusum':
    case 'ewma':
    case 'moving_average':
      return <CircleDot className="w-3.5 h-3.5 text-teal-700" />;

    // 8. Reliability & Survival
    case 'reliability_distribution_analysis':
      return <Hourglass className="w-3.5 h-3.5 text-purple-600" />;
    case 'reliability_life_data_regression':
      return <Clock className="w-3.5 h-3.5 text-purple-600" />;
    case 'reliability_kijima_grp':
      return <Wrench className="w-3.5 h-3.5 text-purple-700" />;

    // 9. Multivariate
    case 'pca':
    case 'factor_analysis':
    case 'cluster_observations':
    case 'cluster_variables':
    case 'cluster_kmeans':
    case 'discriminant_analysis':
    case 'correspondence_analysis':
    case 'item_analysis':
      return <Boxes className="w-3.5 h-3.5 text-fuchsia-600" />;

    // 10. File, Edit, Data, Calc, Help Actions
    case 'file-new':
      return <FilePlus className="w-3.5 h-3.5 text-blue-600" />;
    case 'file-open-project':
    case 'file-sample':
      return <FolderOpen className="w-3.5 h-3.5 text-blue-600" />;
    case 'file-save-project':
    case 'file-save-as-project':
      return <Save className="w-3.5 h-3.5 text-emerald-600" />;
    case 'file-import-xlsx':
      return <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />;
    case 'file-export-xlsx':
      return <FileSpreadsheet className="w-3.5 h-3.5 text-blue-600" />;
    case 'file-import-csv':
      return <Upload className="w-3.5 h-3.5 text-blue-600" />;
    case 'file-export-csv':
    case 'file-export-session':
      return <Download className="w-3.5 h-3.5 text-blue-600" />;
    case 'file-print-report':
      return <Printer className="w-3.5 h-3.5 text-indigo-600" />;



    case 'edit-undo':
      return <Undo2 className="w-3.5 h-3.5 text-blue-600" />;
    case 'edit-redo':
      return <Redo2 className="w-3.5 h-3.5 text-blue-600" />;
    case 'edit-clear-cells':
      return <Eraser className="w-3.5 h-3.5 text-rose-500" />;
    case 'edit-delete-cells':
    case 'edit-clear-sheet':
    case 'edit-clear-session':
      return <Trash2 className="w-3.5 h-3.5 text-rose-600" />;
    case 'edit-copy-cells':
      return <Copy className="w-3.5 h-3.5 text-slate-600" />;
    case 'edit-cut-cells':
      return <Scissors className="w-3.5 h-3.5 text-blue-600" />;
    case 'edit-paste-cells':
      return <ClipboardPaste className="w-3.5 h-3.5 text-amber-600" />;
    case 'edit-insert-col':
    case 'edit-insert-row':
      return <PlusSquare className="w-3.5 h-3.5 text-blue-600" />;
    case 'data-sort':
      return <SortIcon className="w-3.5 h-3.5 text-emerald-600" />;
    case 'data-subset':
      return <Filter className="w-3.5 h-3.5 text-emerald-600" />;
    case 'data-stack':
    case 'data-unstack':
      return <Layers className="w-3.5 h-3.5 text-emerald-600" />;
    case 'data-patterned':
    case 'data-recode':
      return <Grid className="w-3.5 h-3.5 text-emerald-600" />;
    case 'calc-random':
    case 'calc-stats-row':
      return <Calculator className="w-3.5 h-3.5 text-blue-600" />;
    case 'help-about':
      return <Info className="w-3.5 h-3.5 text-blue-600" />;
    case 'help-docs':
      return <HelpCircle className="w-3.5 h-3.5 text-blue-600" />;

    default:
      // Category / Group folder fallback
      if (id.includes('doe') || id.includes('factorial') || id.includes('rsm') || id.includes('taguchi') || id.includes('mixture')) {
        return <Box className="w-3.5 h-3.5 text-cyan-600" />;
      }
      if (id.includes('control') || id.includes('spc') || id.includes('chart')) {
        return <Workflow className="w-3.5 h-3.5 text-teal-600" />;
      }
      if (id.includes('regress')) {
        return <LineChart className="w-3.5 h-3.5 text-indigo-600" />;
      }
      if (id.includes('anova')) {
        return <BarChart className="w-3.5 h-3.5 text-violet-600" />;
      }
      if (id.includes('time') || id.includes('ts_')) {
        return <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />;
      }
      if (id.includes('reliability') || id.includes('survival')) {
        return <Hourglass className="w-3.5 h-3.5 text-purple-600" />;
      }
      if (id.includes('quality') || id.includes('gage') || id.includes('capab')) {
        return <ShieldCheck className="w-3.5 h-3.5 text-sky-600" />;
      }
      if (id.includes('nonparam')) {
        return <ScatterChart className="w-3.5 h-3.5 text-amber-600" />;
      }
      if (id.includes('table')) {
        return <Table className="w-3.5 h-3.5 text-amber-700" />;
      }
      return <BarChart2 className="w-3.5 h-3.5 text-slate-500" />;
  }
};
