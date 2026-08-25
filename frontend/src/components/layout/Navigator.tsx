import React from 'react';
import {
  Badge,
  Button,
} from '@fluentui/react-components';
import {
  TableRegular,
  DataBarHorizontalRegular,
  DeleteRegular,
  ClockRegular,
  ChartMultipleRegular,
  FolderRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';
import { useSessionStore } from '../../store/useSessionStore';

export const Navigator: React.FC = () => {
  const { worksheets, activeSheetId, setActiveSheet } = useWorksheetStore();
  const { items, activeItemId, setActiveItem, removeSessionItem } = useSessionStore();

  return (
    <div className="h-full w-64 min-w-64 max-w-64 bg-[#f8f9fa] border-r border-[#e0e0e0] flex flex-col select-none text-xs">
      {/* Navigator Title */}
      <div className="flex items-center justify-between px-3 py-2 bg-[#eaeef2] border-b border-[#d8dce0] font-semibold text-[#323130]">
        <div className="flex items-center gap-1.5">
          <FolderRegular className="text-[#008450]" />
          <span>Project Navigator</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-[#edebe9]">
        {/* Worksheets Section */}
        <div className="p-2 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-semibold text-[#605e5c] uppercase tracking-wider px-1 py-1">
            <span className="flex items-center gap-1.5">
              <TableRegular className="text-[#008450]" />
              <span>Worksheets</span>
            </span>
            <Badge size="small" appearance="tint" color="brand">
              {worksheets.length}
            </Badge>
          </div>

          <div className="space-y-0.5">
            {worksheets.map((ws) => {
              const isActive = ws.id === activeSheetId;
              const filledRows = ws.rows.filter((r) => Object.values(r).some((v) => v !== undefined && v !== '')).length;

              return (
                <div
                  key={ws.id}
                  onClick={() => setActiveSheet(ws.id)}
                  className={`flex items-center justify-between px-2.5 py-1.5 rounded-md cursor-pointer transition-colors ${
                    isActive
                      ? 'bg-[#ebf3fc] text-[#008450] font-semibold shadow-2xs'
                      : 'hover:bg-[#f0f0f0] text-[#323130]'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate">
                    <TableRegular className={isActive ? 'text-[#008450]' : 'text-[#8a8886]'} />
                    <span className="truncate">{ws.name}</span>
                  </div>
                  <span className="text-[10px] text-[#8a8886]">
                    {filledRows}r
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Session Output History Section */}
        <div className="p-2 space-y-1">
          <div className="flex items-center justify-between text-[11px] font-semibold text-[#605e5c] uppercase tracking-wider px-1 py-1">
            <span className="flex items-center gap-1.5">
              <DataBarHorizontalRegular className="text-[#008450]" />
              <span>Session History</span>
            </span>
            <Badge size="small" appearance="filled" color="brand">
              {items.length}
            </Badge>
          </div>

          {items.length === 0 ? (
            <div className="p-3 text-center text-[#a19f9d] text-xs italic">
              No analyses executed yet.
            </div>
          ) : (
            <div className="space-y-1">
              {items.map((item) => {
                const isSelected = item.id === activeItemId;

                return (
                  <div
                    key={item.id}
                    onClick={() => setActiveItem(item.id)}
                    className={`group flex items-start justify-between p-2 rounded-md cursor-pointer transition-all border ${
                      isSelected
                        ? 'bg-[#ebf3fc] border-[#008450] text-[#008450] shadow-xs'
                        : 'bg-white hover:bg-[#f5f5f5] border-[#e0e0e0] text-[#323130]'
                    }`}
                  >
                    <div className="flex items-start gap-1.5 overflow-hidden">
                      <ChartMultipleRegular className={`mt-0.5 shrink-0 ${isSelected ? 'text-[#008450]' : 'text-[#8a8886]'}`} />
                      <div className="overflow-hidden">
                        <div className="font-semibold truncate text-[11.5px]">
                          {item.result.title}
                        </div>
                        {item.result.subtitle && (
                          <div className="text-[10px] text-[#605e5c] truncate">
                            {item.result.subtitle}
                          </div>
                        )}
                        <div className="flex items-center gap-1.5 text-[10px] text-[#8a8886] mt-0.5">
                          <ClockRegular className="w-3 h-3 inline" />
                          <span>{item.timestamp}</span>
                          <span>•</span>
                          <span className="truncate">{item.worksheetName}</span>
                        </div>
                      </div>
                    </div>

                    <Button
                      appearance="subtle"
                      size="small"
                      icon={<DeleteRegular />}
                      title="Delete Output"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSessionItem(item.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 text-[#a19f9d] hover:text-[#d13438] shrink-0"
                      style={{ minWidth: '24px', height: '24px', padding: '0' }}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
