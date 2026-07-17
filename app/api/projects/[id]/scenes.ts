import { NextApiRequest, NextApiResponse } from 'next';

const scenesByProjectId: Record<string, any[]> = {};

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const { id } = req.query;
  
  if (req.method !== 'GET') {
    res.setHeader('Allow', ['GET']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const scenes = scenesByProjectId[id as string] || [];
  res.status(200).json(scenes);
}