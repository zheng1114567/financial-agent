import React from 'react';

interface ModelSelectorProps {
  currentModel: string;
  version: string;
  onModelChange: (model: string) => void;
}

const ModelSelector: React.FC<ModelSelectorProps> = ({
  currentModel,
  version,
  onModelChange,
}) => {
  const models = [
    { id: 'qwen-plus', name: 'Qwen Plus', version: 'v2.3.391' },
    { id: 'qwen-max', name: 'Qwen Max', version: 'v2.3.391' },
    { id: 'qwen-turbo', name: 'Qwen Turbo', version: 'v2.3.391' },
  ];

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-500">Model:</span>
      <select
        value={currentModel}
        onChange={(e) => onModelChange(e.target.value)}
        className="px-3 py-1.5 bg-white border border-gray-300 rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.name} {model.version}
          </option>
        ))}
      </select>
      <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full">
        {version}
      </span>
    </div>
  );
};

export default ModelSelector;