import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const scenesDir = path.join(process.cwd(), 'data', 'scenes');
if (!fs.existsSync(scenesDir)) {
  fs.mkdirSync(scenesDir);
}

export async function GET(request: Request) {
  const id = request.nextUrl.pathname.split('/').pop();
  if (!id) {
    return NextResponse.json({ error: 'Invalid project ID' }, { status: 400 });
  }

  const scenesPath = path.join(scenesDir, `${id}.json`);
  if (!fs.existsSync(scenesPath)) {
    return NextResponse.json([], { status: 200 });
  }

  try {
    const scenesData = fs.readFileSync(scenesPath, 'utf-8');
    return NextResponse.json(JSON.parse(scenesData), { status: 200 });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to read scenes data' }, { status: 500 });
  }
}