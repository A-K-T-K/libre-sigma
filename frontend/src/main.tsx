import React, { Component, ErrorInfo, ReactNode } from 'react';
import ReactDOM from 'react-dom/client';
import { FluentProvider, createLightTheme, BrandVariants } from '@fluentui/react-components';
import App from './App';
import './index.css';
import 'katex/dist/katex.min.css';

// Pantone Classic Green (Pantone 347 C / Emerald Green) Theme
const pantoneGreenBrand: BrandVariants = {
  10: '#022112',
  20: '#063B21',
  30: '#0A5330',
  40: '#0C653B',
  50: '#0E7746',
  60: '#0F8850',
  70: '#008450',
  80: '#00965C',
  90: '#00A86B',
  100: '#14B877',
  110: '#2EC787',
  120: '#4DD498',
  130: '#70E1AB',
  140: '#97ECC0',
  150: '#C0F5D7',
  160: '#E6FAF0',
};

const pantoneTheme = createLightTheme(pantoneGreenBrand);

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('OpenMinitab Uncaught Error:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen w-screen flex flex-col items-center justify-center bg-[#f3f2f1] text-[#201f1e] p-6 font-sans">
          <div className="bg-white border border-[#d2d0ce] rounded-xl shadow-xl p-6 max-w-md w-full text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto text-xl font-bold">
              !
            </div>
            <h2 className="text-base font-bold text-[#201f1e]">Something went wrong</h2>
            <p className="text-xs text-[#605e5c]">
              {this.state.error?.message || 'An unexpected rendering error occurred.'}
            </p>
            <button
              onClick={this.handleReload}
              className="px-4 py-2 bg-[#008450] hover:bg-[#007244] text-white rounded-md text-xs font-semibold shadow-sm transition-colors"
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <FluentProvider theme={pantoneTheme} className="h-full w-full">
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </FluentProvider>
  </React.StrictMode>,
);
