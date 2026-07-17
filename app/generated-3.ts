import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const videosDir = path.join(process.cwd(), 'data', 'videos');
if (!fs.existsSync(videosDir)) {
  fs.mkdirSync(videosDir);
}

export async function POST(request: Request) {
  const formData = await request.formData();
  
  if (!formData || !formData.has('file')) {
    return NextResponse.json({ error: 'No file provided' }, { status: 400 });
  }

  const file = formData.get('file');
  
  if (!file) {
    return NextResponse.json({ error: 'No file provided' }, { status: 400 });
  }
  
  if (!(file instanceof File)) {
    return NextResponse.json({ error: 'Invalid file type' }, { status: 400 });
  }

  const maxSize = 1024 * 1024 * 50; // 50MB limit
  if (file.size > maxSize) {
    return NextResponse.json({ error: `File size exceeds maximum of ${maxSize / (1024 * 1024)}MB` }, { status: 400 });
  }

  const allowedExtensions = ['.mp4', '.avi', '.mov', '.mkv'];
  const fileExtension = path.extname(file.name).toLowerCase();
  
  if (!allowedExtensions.includes(fileExtension)) {
    return NextResponse.json({ error: `Invalid file extension. Allowed: ${allowedExtensions.join(', ')}` }, { status: 400 });
  }

  const filePath = path.join(videosDir, file.name);
  const writeStream = fs.createWriteStream(filePath);

  await new Promise((resolve, reject) => {
    file.stream().pipe(writeStream).on('finish', resolve).on('error', reject);
  });

  return NextResponse.json({ message: 'File uploaded successfully' }, { status: 201 });
}