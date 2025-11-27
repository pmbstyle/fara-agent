import React from 'react';
import { Monitor, Image as ImageIcon } from 'lucide-react';

const LiveView = ({ screenshot }) => {
  return (
    <div className="flex-1 flex flex-col h-full bg-black text-white w-1/2">
      <div className="p-4 border-b border-gray-800 flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Monitor size={20} className="text-green-400" />
          Live View
        </h2>
        {screenshot && (
          <span className="text-xs text-green-400 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Live
          </span>
        )}
      </div>

      <div className="flex-1 p-4 flex items-center justify-center bg-gray-950 overflow-hidden relative">
        {screenshot ? (
          <div className="relative w-full h-full flex items-center justify-center">
             <img
               src={screenshot}
               alt="Browser View"
               className="max-w-full max-h-full object-contain rounded border border-gray-800 shadow-2xl"
             />
          </div>
        ) : (
          <div className="text-center text-gray-500">
            <ImageIcon size={48} className="mx-auto mb-2 opacity-50" />
            <p>Waiting for browser stream...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LiveView;
