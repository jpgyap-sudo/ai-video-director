import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const videosDir = path.join(process.cwd(), 'data', 'videos');
if (!fs.existsSync(videosDir)) {
  fs.mkdirSync(videosDir, { recursive: true });
}

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    
    if (!formData.has('file')) {
      return NextResponse.json({ error: 'No file provided' }, { status: 400 });
    }

    const file = formData.get('file');
    
    if (typeof file === 'string') {
      return NextResponse.json({ error: 'Invalid request format. Expected FormData.' }, { status: 400 });
    }

    if (!(file instanceof File)) {
      return NextResponse.json({ error: 'File field must be a valid File object' }, { status: 400 });
    }

    // Validate file type (only accept video files)
    const allowedTypes = ['video/mp4', 'video/webm', 'video/quicktime'];
    if (!allowedTypes.includes(file.type)) {
      return NextResponse.json({ error: 'Invalid file type. Only MP4, WebM, and MOV are allowed.' }, { status: 400 });
    }

    // Validate file size (max 100MB)
    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
      return NextResponse.json({ error: 'File too large. Maximum size is 100MB.' }, { status: 400 });
    }

    // Sanitize filename to prevent path traversal attacks
    const sanitizedFileName = file.name.split(/[\\/]/).pop() || `video-${Date.now()}`;
    const filePath = path.join(videosDir, sanitizedFileName);

    try {
      await new Promise<void>((resolve, reject) => {
        fs.mkdirSync(path.dirname(filePath), { recursive: true });
        
        const writeStream = fs.createWriteStream(filePath);
        
        file.stream().pipe(writeStream)
          .on('finish', () => resolve())
          .on('error', (err: Error) => {
            try {
              if (fs.existsSync(filePath)) {
                fs.unlinkSync(filePath);
              }
            } catch { /* ignore cleanup errors */ }
            reject(err);
          });
      });

      return NextResponse.json({ message: 'File uploaded successfully' }, { status: 201 });
    } finally {
      // Ensure directory exists even if stream fails
      try {
        fs.mkdirSync(path.dirname(filePath), { recursive: true });
      } catch { /* ignore */ }
    }
  } catch (error) {
    console.error('Upload failed:', error);
    
    // Clean up partial uploads on server errors
    const sanitizedFileName = 'video-' + Date.now();
    try {
      if (fs.existsSync(path.join(videosDir, sanitizedFileName))) {
        fs.unlinkSync(path.join(videosDir, sanitizedFileName));
      }
    } catch { /* ignore */ }
    
    return NextResponse.json({ error: 'Failed to upload file. Please try again.' }, { status: 500 });
  }
}