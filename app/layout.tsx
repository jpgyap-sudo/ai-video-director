"use client";

import React from 'react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}