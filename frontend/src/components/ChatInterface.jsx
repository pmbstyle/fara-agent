import React, { useState, useEffect, useRef } from 'react';
import { Send, Image as ImageIcon, Terminal, Play, Loader, AlertCircle } from 'lucide-react';

const ChatInterface = ({ messages, task, setTask, onStart, isRunning, status }) => {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, status]);

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100 border-r border-gray-800 w-1/2">
      <div className="p-4 border-b border-gray-800 bg-gray-900 sticky top-0 z-10">
        <h2 className="text-xl font-bold flex items-center gap-2 text-white">
          <Terminal size={20} className="text-blue-400" />
          Fara Agent
        </h2>
        <p className="text-xs text-gray-400 mt-1">
          Local browser automation agent
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`p-3 rounded-lg text-sm ${
            msg.type === 'model_response' ? 'bg-gray-800 border border-gray-700' :
            msg.type === 'action_result' ? 'bg-gray-800/50 border border-gray-700/50 text-gray-300' :
            msg.type === 'error' ? 'bg-red-900/20 border border-red-800/50 text-red-200' :
            'bg-gray-800/30'
          }`}>
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                msg.type === 'model_response' ? 'bg-blue-900/50 text-blue-200' :
                msg.type === 'action_result' ? 'bg-green-900/50 text-green-200' :
                msg.type === 'error' ? 'bg-red-900/50 text-red-200' :
                'bg-gray-700 text-gray-300'
              }`}>
                {msg.type === 'model_response' ? 'THOUGHT' :
                 msg.type === 'action_result' ? 'ACTION' :
                 msg.type.toUpperCase()}
              </span>
            </div>
            <pre className="whitespace-pre-wrap font-sans">
              {msg.content}
            </pre>
            {msg.action && (
              <div className="mt-2 text-xs font-mono text-gray-500 bg-gray-950/50 p-2 rounded">
                 {JSON.stringify(msg.action, null, 2)}
              </div>
            )}
          </div>
        ))}
        {status && (
           <div className="flex items-center gap-2 text-gray-400 text-sm animate-pulse">
              <Loader size={14} className="animate-spin"/>
              {status}
           </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-gray-800 bg-gray-900">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (task.trim() && !isRunning) onStart();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Enter a task (e.g., 'Go to wikipedia and search for cats')"
            className="flex-1 bg-gray-800 border-gray-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            disabled={isRunning}
          />
          <button
            type="submit"
            disabled={!task.trim() || isRunning}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
          >
            {isRunning ? <Loader size={18} className="animate-spin" /> : <Play size={18} />}
            Run
          </button>
        </form>
      </div>
    </div>
  );
};

export default ChatInterface;
