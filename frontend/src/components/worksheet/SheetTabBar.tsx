import React, { useState } from 'react';
import {
  Button,
  Input,
} from '@fluentui/react-components';
import {
  AddRegular,
  DismissRegular,
  TableRegular,
} from '@fluentui/react-icons';
import { useWorksheetStore } from '../../store/useWorksheetStore';

export const SheetTabBar: React.FC = () => {
  const { worksheets, activeSheetId, setActiveSheet, createSheet, deleteSheet, renameSheet } = useWorksheetStore();
  const [editingSheetId, setEditingSheetId] = useState<string | null>(null);
  const [editName, setEditName] = useState<string>('');

  const handleStartRename = (sheetId: string, currentName: string) => {
    setEditingSheetId(sheetId);
    setEditName(currentName);
  };

  const handleCommitRename = () => {
    if (editingSheetId && editName.trim()) {
      renameSheet(editingSheetId, editName.trim());
    }
    setEditingSheetId(null);
  };

  return (
    <div className="flex items-center bg-[#f3f2f1] border-t border-[#d2d0ce] px-2 py-0.5 space-x-1 select-none overflow-x-auto text-xs sheet-tab-bar">

      {worksheets.map((sheet) => {
        const isActive = sheet.id === activeSheetId;
        const isEditing = editingSheetId === sheet.id;

        return (
          <div
            key={sheet.id}
            onClick={() => setActiveSheet(sheet.id)}
            onDoubleClick={() => handleStartRename(sheet.id, sheet.name)}
            className={`group flex items-center gap-1.5 px-3 py-1 rounded-t border-t-2 border-l border-r transition-all cursor-pointer ${
              isActive
                ? 'bg-white border-t-[#008450] border-l-[#d2d0ce] border-r-[#d2d0ce] text-[#008450] font-semibold shadow-xs -mb-px'
                : 'bg-[#edebe9] hover:bg-[#f5f5f5] border-transparent text-[#605e5c]'
            }`}
          >
            <TableRegular className={`w-3.5 h-3.5 ${isActive ? 'text-[#008450]' : 'text-[#8a8886]'}`} />
            {isEditing ? (
              <Input
                size="small"
                value={editName}
                onChange={(_, data) => setEditName(data.value)}
                onBlur={handleCommitRename}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCommitRename();
                  if (e.key === 'Escape') setEditingSheetId(null);
                }}
                autoFocus
                style={{ width: '100px', height: '22px', fontSize: '11px' }}
              />
            ) : (
              <span className="truncate max-w-[120px]">{sheet.name}</span>
            )}

            {worksheets.length > 1 && (
              <Button
                appearance="subtle"
                size="small"
                icon={<DismissRegular className="w-3 h-3" />}
                title="Delete Worksheet"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSheet(sheet.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-[#8a8886] hover:text-[#d13438]"
                style={{ minWidth: '18px', width: '18px', height: '18px', padding: 0 }}
              />
            )}
          </div>
        );
      })}

      <Button
        appearance="subtle"
        size="small"
        icon={<AddRegular />}
        title="Add New Worksheet"
        onClick={() => createSheet()}
        style={{ minWidth: '24px', height: '24px', padding: '0 4px' }}
      />
    </div>
  );
};
