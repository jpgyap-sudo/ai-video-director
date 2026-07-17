'use client';
import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Video {
  id: number;
  name: string;
}

const Dashboard = () => {
  const [videos, setVideos] = useState<Video[]>([]);
  const [selectedVideoId, setSelectedVideoId] = useState<number | null>(null);

  useEffect(() => {
    fetch('/api/videos/upload')
      .then(response => response.json())
      .then(data => setVideos(data as Video[]));
  }, []);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const fileInput = event.target.files?.[0];
    if (!fileInput) return;

    const formData = new FormData();
    formData.append('file', fileInput);

    await axios.post('/api/videos/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    setVideos(prevVideos => [...prevVideos, { id: Date.now(), name: fileInput.name }]);
  };

  const handleVideoClick = (id: number) => {
    setSelectedVideoId(id);
  };

  return (
    <div>
      <h1>Video Upload Dashboard</h1>
      <input type="file" onChange={handleUpload} />
      <ul>
        {videos.map(video => (
          <li key={video.id} onClick={() => handleVideoClick(video.id)}>
            {video.name}
          </li>
        ))}
      </ul>
      {selectedVideoId && (
        <div>
          <h2>Detected Scenes</h2>
          <button onClick={() => setSelectedVideoId(null)}>Back to List</button>
          {/* Add code to fetch and display detected scenes */}
        </div>
      )}
    </div>
  );
};

export default Dashboard;