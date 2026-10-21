import { env } from '$env/dynamic/private';

const base = () => (env.PREFECT_API_URL || 'http://127.0.0.1:4200/api').replace(/\/$/, '');

async function api<T>(path: string, body?: unknown): Promise<T> {
	const response = await fetch(base() + path, {
		method: body === undefined ? 'GET' : 'POST',
		headers: { 'content-type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body),
		signal: AbortSignal.timeout(3000)
	});
	if (!response.ok) throw new Error(`Prefect HTTP ${response.status}`);
	return response.json() as Promise<T>;
}

type Deployment = {
	id: string;
	name: string;
	paused: boolean;
	status: string;
	schedules: { active: boolean; schedule: { cron?: string; timezone?: string } }[];
};
type FlowRun = {
	id: string;
	name: string;
	state_type: string;
	state_name: string;
	start_time: string | null;
	end_time: string | null;
	total_run_time: number | null;
	parameters: Record<string, unknown>;
	state?: { message: string | null };
};

export async function prefectStatus() {
	try {
		const [deployments, runs] = await Promise.all([
			api<Deployment[]>('/deployments/filter', { limit: 20 }),
			api<FlowRun[]>('/flow_runs/filter', { limit: 8, sort: 'START_TIME_DESC' })
		]);
		return {
			available: true,
			error: null,
			deployments,
			runs,
			uiUrl: (env.PREFECT_UI_URL || 'http://127.0.0.1:4200').replace(/\/$/, '')
		};
	} catch (error) {
		return {
			available: false,
			error: error instanceof Error ? error.message : 'Prefect nicht erreichbar',
			deployments: [] as Deployment[],
			runs: [] as FlowRun[],
			uiUrl: (env.PREFECT_UI_URL || 'http://127.0.0.1:4200').replace(/\/$/, '')
		};
	}
}
