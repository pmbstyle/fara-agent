import React, { useState, useEffect, useRef } from 'react';
import ChatInterface from './components/ChatInterface';
import LiveView from './components/LiveView';

function App() {
  const [task, setTask] = useState('');
  const [messages, setMessages] = useState([]);
  const [screenshot, setScreenshot] = useState(null);
  const [status, setStatus] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    // Connect to WebSocket
    const connect = () => {
      const ws = new WebSocket('ws://localhost:8000/ws');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Connected to WebSocket');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'screenshot') {
            setScreenshot(data.image);
          } else if (data.type === 'status') {
            setStatus(data.content);
            if (data.content === "Agent finished.") {
               setIsRunning(false);
            } else if (data.content === "Agent starting...") {
               setIsRunning(true);
            }
          } else if (data.type === 'error') {
             setMessages(prev => [...prev, { type: 'error', content: data.content }]);
             setIsRunning(false);
             setStatus('Error occurred');
          } else {
            // Logs, thoughts, actions
            setMessages(prev => [...prev, data]);
          }
        } catch (e) {
          console.error('Failed to parse message', e);
        }
      };

      ws.onclose = () => {
        console.log('Disconnected from WebSocket');
        setStatus('Disconnected');
        setIsRunning(false);
        // Reconnect logic could go here
        setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
         console.error("WS Error", err);
         setStatus('Connection Error');
      };
    };

    connect();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleStart = () => {
    if (!task.trim()) return;

    setMessages([]);
    setScreenshot(null);
    setIsRunning(true);
    setStatus('Initializing...');

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'start_task',
        task: task
      }));
    } else {
       console.error("Websocket not connected");
       setStatus("Connection lost. Please wait...");
    }
  };

  const handleStop = () => {
     if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
         wsRef.current.send(JSON.stringify({
             type: 'stop_task'
         }));
         setStatus('Stopping...');
     }
  };

  return (
    <div className="flex h-screen w-full bg-black">
      <ChatInterface
        messages={messages}
        task={task}
        setTask={setTask}
        onStart={handleStart}
        onStop={handleStop}
        isRunning={isRunning}
        status={status}
      />
      <LiveView screenshot={screenshot} />
    </div>
  );
}

export default App;
