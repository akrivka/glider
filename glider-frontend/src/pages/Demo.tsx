import type { Component } from 'solid-js';
import { createSignal, onCleanup, Show } from 'solid-js';

interface WorkflowStatus {
  workflow_id: string;
  status: string;
  result: string | null;
}

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

export const DemoPage: Component = () => {
  const [workflowId, setWorkflowId] = createSignal<string | null>(null);
  const [status, setStatus] = createSignal<WorkflowStatus | null>(null);
  const [loading, setLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);
  const [sleepSeconds, setSleepSeconds] = createSignal(5);
  const [message, setMessage] = createSignal('');

  let pollInterval: number | undefined;

  const startWorkflow = async () => {
    setLoading(true);
    setError(null);
    setStatus(null);

    try {
      const response = await fetch(`${API_BASE}/api/workflows/demo/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sleep_seconds: sleepSeconds(), message: message() }),
      });

      if (!response.ok) throw new Error('Failed to start workflow');

      const data = await response.json();
      setWorkflowId(data.workflow_id);

      pollStatus(data.workflow_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const pollStatus = (id: string) => {
    if (pollInterval) clearInterval(pollInterval);

    const checkStatus = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/workflows/demo/${id}/status`);
        if (!response.ok) throw new Error('Failed to get status');

        const data: WorkflowStatus = await response.json();
        setStatus(data);

        if (data.status === 'completed' && pollInterval) {
          clearInterval(pollInterval);
          pollInterval = undefined;
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
        if (pollInterval) clearInterval(pollInterval);
      }
    };

    checkStatus();
    pollInterval = setInterval(checkStatus, 500);
  };

  onCleanup(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  return (
    <div class="max-w-2xl mx-auto px-6">
      <h2 class="text-2xl font-bold mb-6">Temporal Workflow Demo</h2>

      <div class="bg-gray-50 p-6 rounded-lg mb-6">
        <p class="text-gray-600 mb-4">
          This demo starts a Temporal workflow that sleeps for a configurable duration and
          optionally stores a message in SurrealDB. You can watch the workflow progress in
          real-time.
        </p>

        <div class="flex items-center gap-4 mb-4">
          <label class="text-gray-700">Sleep duration (seconds):</label>
          <input
            type="number"
            min="1"
            max="60"
            value={sleepSeconds()}
            onInput={(e) => setSleepSeconds(parseInt(e.currentTarget.value) || 5)}
            class="border rounded px-3 py-2 w-20"
          />
        </div>

        <div class="mb-4">
          <label class="text-gray-700 block mb-2">Message to store in SurrealDB (optional):</label>
          <input
            type="text"
            value={message()}
            onInput={(e) => setMessage(e.currentTarget.value)}
            placeholder="Enter a message to store..."
            class="border rounded px-3 py-2 w-full"
          />
        </div>

        <button
          onClick={startWorkflow}
          disabled={loading()}
          class="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading() ? 'Starting...' : 'Start Workflow'}
        </button>
      </div>

      <Show when={error()}>
        <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error()}
        </div>
      </Show>

      <Show when={workflowId()}>
        <div class="bg-white border rounded-lg p-6">
          <h3 class="font-semibold mb-4">Workflow Status</h3>

          <div class="space-y-2">
            <p>
              <span class="text-gray-500">Workflow ID:</span>{' '}
              <code class="bg-gray-100 px-2 py-1 rounded text-sm">{workflowId()}</code>
            </p>

            <Show when={status()}>
              <p>
                <span class="text-gray-500">Status:</span>{' '}
                <span
                  class={`px-2 py-1 rounded text-sm ${
                    status()?.status === 'completed'
                      ? 'bg-green-100 text-green-800'
                      : status()?.status === 'running'
                        ? 'bg-yellow-100 text-yellow-800'
                        : status()?.status === 'storing'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {status()?.status}
                </span>
              </p>

              <Show when={status()?.result}>
                <p>
                  <span class="text-gray-500">Result:</span> {status()?.result}
                </p>
              </Show>
            </Show>
          </div>
        </div>
      </Show>

      <div class="mt-8 text-sm text-gray-500">
        <p>
          View the workflow in{' '}
          <a href="http://localhost:8080" target="_blank" class="text-blue-600 hover:underline">
            Temporal UI
          </a>
        </p>
      </div>
    </div>
  );
};
