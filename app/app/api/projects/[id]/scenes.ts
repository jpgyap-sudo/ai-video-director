import { NextApiRequest, NextApiResponse } from 'next';

const scenesByProjectId: any = {};

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const { id } = req.query;
  if (req.method === 'GET') {
    const scenes = scenesByProjectId[id] || [];
    res.status(200).json(scenes);
  } else {
    res.setHeader('Allow', ['GET']);
    res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}