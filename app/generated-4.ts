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
    return NextResponse.json({ error: 'Invalid project ID' }, { status: 400, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET', 'Access-Control-Allow-Headers': 'Content-Type' } });
  }

  const scenesPath = path.join(scenesDir, `${id}.json`);
  if (!fs.existsSync(scenesPath)) {
    return NextResponse.json({ error: 'Scenes file not found' }, { status: 404, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET', 'Access-Control-Allow-Headers': 'Content-Type' } });
  }

  try {
    const scenesData = fs.readFileSync(scenesPath, 'utf-8');
    return NextResponse.json(JSON.parse(scenesData), { status: 200, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET', 'Access-Control-Allow-Headers': 'Content-Type' } });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to read scenes data' }, { status: 500, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET', 'Access-Control-Allow-Headers': 'Content-Type' } });
  }
}