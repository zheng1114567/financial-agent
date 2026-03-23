import React from 'react';

interface SidebarItem {
  id: string;
  title: string;
  lastMessage?: string;
  timestamp: string;
  isCurrent?: boolean;
}

const Sidebar: React.FC<{
  items: SidebarItem[];
  onRename: (id: string, newTitle: string) => void;
  onDelete: (id: string) => void;
  onExport: (id: string) => void;
  onCreateNew: () => void;
}> = ({ items, onRename, onDelete, onExport, onCreateNew }) => {
  return (
    <aside className="sidebar flex flex-col border-r border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <h2 className="font-semibold text-gray-700 mb-3">Chat History</h2>
        <button
          onClick={onCreateNew}
          className="w-full py-2 px-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium flex items-center justify-center gap-1"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 5V19M5 12H19" stroke="white" strokeWidth="2" strokeLinecap="round" />
          </svg>
          New Chat
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {items.map((item) => (
          <div
            key={item.id}
            className={`px-3 py-2 rounded-md cursor-pointer flex items-center justify-between transition-colors ${
              item.isCurrent
                ? 'bg-blue-50 border-l-4 border-blue-500 text-blue-800'
                : 'hover:bg-gray-100 text-gray-700'
            }`}
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{item.title}</p>
              <p className="text-xs text-gray-500 truncate">{item.lastMessage || 'No messages'}</p>
            </div>
            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                onClick={() => onRename(item.id, prompt('Enter new title:', item.title) || item.title)}
                className="p-1 text-gray-500 hover:text-blue-600"
                aria-label="Rename"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M11 4H7C5.89543 4 5 4.89543 5 6V20C5 21.1046 5.89543 22 7 22H17C18.1046 22 19 21.1046 19 20V16M18.5 7.5L13 2M21 4.5L15.5 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <button
                onClick={() => onDelete(item.id)}
                className="p-1 text-gray-500 hover:text-red-600"
                aria-label="Delete"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M3 6H5H21M8 6V21C8 21.5523 8.44772 22 9 22H15C15.5523 22 16 21.5523 16 21V6M18.5 6L17.5 21C17.5 21.5523 17.0523 22 16.5 22H7.5C7.22386 22 7 21.7761 7 21.5L8 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <button
                onClick={() => onExport(item.id)}
                className="p-1 text-gray-500 hover:text-green-600"
                aria-label="Export"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15M12 10L12 21M12 10L15 7M12 10L9 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
};

export default Sidebar;