import React from 'react';
import {
  Button,
} from '@fluentui/react-components';
import {
  SparkleRegular,
  DismissRegular,
  LayerDiagonalRegular,
  CodeRegular,
  FlashRegular,
} from '@fluentui/react-icons';

interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AboutModal: React.FC<AboutModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-md overflow-hidden flex flex-col animate-in zoom-in-95 duration-100">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
          <div className="flex items-center space-x-2">
            <img src="/logo.svg" alt="LibRE Tab" className="w-5 h-5 rounded shadow-xs" />
            <h2 className="text-sm font-bold text-[#201f1e]">
              About LibRE Tab
            </h2>
          </div>
          <Button
            appearance="subtle"
            size="small"
            icon={<DismissRegular />}
            onClick={onClose}
            style={{ minWidth: '28px', padding: 0 }}
          />
        </div>

        {/* Content */}
        <div className="p-5 space-y-4 text-xs text-[#605e5c] leading-relaxed">
          <div className="bg-[#ebf3fc] border border-[#c7e0f4] rounded-lg p-3.5 text-[#008450]">
            <div className="font-bold text-sm text-[#008450] mb-1 flex items-center gap-1.5">
              <SparkleRegular className="w-4 h-4" />
              <span>LibRE Tab v1.0.0</span>
            </div>
            <p className="text-[11.5px] text-[#0c3b5e]">
              Modular, high-density scientific statistical analysis & reliability engineering platform.
            </p>
          </div>


          <div className="space-y-3 pt-1">
            <div className="flex items-start gap-2.5">
              <LayerDiagonalRegular className="text-[#008450] mt-0.5 shrink-0 w-4 h-4" />
              <div>
                <strong className="text-[#201f1e]">Schema-Driven Plugin Architecture:</strong> Add new statistical modules as single Python files in <code>backend/app/plugins/modules/</code>. Dynamic menus and forms render automatically.
              </div>
            </div>

            <div className="flex items-start gap-2.5">
              <CodeRegular className="text-[#881798] mt-0.5 shrink-0 w-4 h-4" />
              <div>
                <strong className="text-[#201f1e]">Scientific Computing Stack:</strong> Powered by FastAPI, SciPy, Statsmodels, NumPy, and Pandas.
              </div>
            </div>

            <div className="flex items-start gap-2.5">
              <FlashRegular className="text-[#ca5010] mt-0.5 shrink-0 w-4 h-4" />
              <div>
                <strong className="text-[#201f1e]">Interactive Visualizations:</strong> High-performance Plotly charts with density curves, boxplots, residual plots, and Taguchi response charts.
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex justify-end">
          <Button appearance="primary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
