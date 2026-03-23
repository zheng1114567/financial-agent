import React from 'react';

const NotFoundPage: React.FC = () => {
  return (
    <div id="ice-container" className="min-h-screen flex flex-col items-center justify-center bg-gray-900 text-white">
      <div className="text-center p-8 max-w-md">
        <h1 className="text-6xl font-bold mb-4">404</h1>
        <h2 className="text-2xl font-semibold mb-2">Page Not Found</h2>
        <p className="text-gray-400 mb-6">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="space-x-4">
          <a 
            href="/" 
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Go Home
          </a>
          <a 
            href="/history" 
            className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
          >
            View History
          </a>
        </div>
      </div>
    </div>
  );
};

export default NotFoundPage;