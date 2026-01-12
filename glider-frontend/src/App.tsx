import type { Component } from 'solid-js';
import { Outline } from './components/Outline';

const App: Component = () => {
  return (
    <div class="min-h-screen bg-white">
      <header class="border-b border-gray-200 py-4 px-6">
        <h1 class="text-xl font-semibold text-gray-800">Glider</h1>
      </header>
      <main class="py-6">
        <Outline />
      </main>
    </div>
  );
};

export default App;
