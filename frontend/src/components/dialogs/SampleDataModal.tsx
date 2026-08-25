import React, { useEffect, useState } from 'react';
import {
  Button,
  Badge,
  Spinner,
} from '@fluentui/react-components';
import {
  DatabaseRegular,
  DismissRegular,
} from '@fluentui/react-icons';
import { fetchSampleDataset, fetchSampleDatasets } from '../../services/api';
import { ColumnDef, SampleDatasetMeta } from '../../types';
import { useWorksheetStore } from '../../store/useWorksheetStore';

interface SampleDataModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SampleDataModal: React.FC<SampleDataModalProps> = ({ isOpen, onClose }) => {
  const [datasets, setDatasets] = useState<SampleDatasetMeta[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const { loadDataset } = useWorksheetStore();

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      fetchSampleDatasets()
        .then((data) => setDatasets(data))
        .catch((err) => console.error('Error loading sample datasets:', err))
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSelectDataset = async (datasetMeta: SampleDatasetMeta) => {
    setLoadingId(datasetMeta.id);
    try {
      const data = await fetchSampleDataset(datasetMeta.id);
      const cols: ColumnDef[] = (data.columns || []).map((col) => ({
        id: col.id,
        name: col.name,
        type: (col.type === 'text' || col.type === 'date' ? col.type : 'numeric'),
      }));
      loadDataset(data.name, cols, data.rows);
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-[1px] p-4 select-none animate-in fade-in duration-100"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-lg shadow-2xl border border-[#d2d0ce] w-full max-w-lg overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-100">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-[#f8f9fa] border-b border-[#e0e0e0]">
          <div className="flex items-center space-x-2">
            <DatabaseRegular className="text-[#008450]" />
            <h2 className="text-sm font-bold text-[#201f1e]">
              Open Sample Statistical Datasets
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

        {/* List of Datasets */}
        <div className="p-4 space-y-2.5 max-h-[60vh] overflow-y-auto">
          {loading ? (
            <div className="py-10 flex flex-col items-center justify-center text-[#605e5c] gap-2">
              <Spinner size="medium" label="Loading sample datasets..." />
            </div>
          ) : datasets.length === 0 ? (
            <div className="text-center py-6 text-[#8a8886] text-xs">
              No sample datasets found.
            </div>
          ) : (
            datasets.map((d) => (
              <div
                key={d.id}
                onClick={() => handleSelectDataset(d)}
                className="group p-3 border border-[#e0e0e0] hover:border-[#008450] bg-white hover:bg-[#ebf3fc]/40 rounded-lg cursor-pointer transition-all shadow-2xs"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-[#201f1e] group-hover:text-[#008450]">
                      {d.name}
                    </h3>
                    <p className="text-[11.5px] text-[#605e5c] mt-0.5 leading-relaxed">
                      {d.description}
                    </p>
                  </div>
                  <div className="shrink-0 ml-3">
                    {loadingId === d.id ? (
                      <Spinner size="tiny" />
                    ) : (
                      <Badge size="small" appearance="tint" color="brand">
                        {d.row_count} rows
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-[#f8f9fa] border-t border-[#e0e0e0] flex justify-end">
          <Button appearance="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
