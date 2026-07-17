'use client';
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Video {
  id: number;
  name: string;
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_: Error) {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <div>An unexpected error occurred. Please refresh the page.</div>;
    }

    return this.props.children;
  }
}

const Dashboard = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<number | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    fetch('/api/videos/upload')
      .then((response) => {
        if (!isMounted) return;
        throw new Error('Videos endpoint only supports POST');
      })
      .catch(() => {
        if (isMounted) setVideos([]);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileInput = event.target.files?.[0];
    if (!fileInput) return;

    try {
      const formData = new FormData();
      formData.append('file', fileInput);

      await axios.post('/api/videos/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setVideos((prevVideos) => [...prevVideos, { id: Date.now(), name: fileInput.name }]);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      event.target.value = '';
    }
  };

  const handleVideoClick = (id: number) => {
    setSelectedVideoId(id);
  };

  return (
    <div>
      <h1>Video Upload Dashboard</h1>
      <input type="file" onChange={handleUpload} />
      <ul>
        {videos.map((video) => (
          <li key={video.id} onClick={() => handleVideoClick(video.id)}>
            {video.name}
          </li>
        ))}
      </ul>
      {selectedVideoId && !loading && (
        <div>
          <h2>Detected Scenes</h2>
          <button onClick={() => setSelectedVideoId(null)}>Back to List</button>
          {/* Add code to fetch and display detected scenes */}
        </div>
      )}
    </div>
  );
};

export default function Page() {
  return (
    <ErrorBoundary>
      <Dashboard />
    </ErrorBoundary>
  );
}