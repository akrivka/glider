import type { Component, ParentProps } from 'solid-js';
import { A } from '@solidjs/router';

const App: Component<ParentProps> = (props) => {
  return (
    <div class="min-h-screen bg-white">
      <header class="border-b border-gray-200 py-4 px-6 flex items-center justify-between">
        <h1 class="text-xl font-semibold text-gray-800">
          <A href="/">Glider</A>
        </h1>
        <nav class="flex gap-4">
          <A
            href="/"
            class="text-gray-600 hover:text-gray-900"
            activeClass="font-semibold text-gray-900"
            end
          >
            Outline
          </A>
          <A
            href="/demo"
            class="text-gray-600 hover:text-gray-900"
            activeClass="font-semibold text-gray-900"
          >
            Demo
          </A>
        </nav>
      </header>
      <main class="py-6">{props.children}</main>
    </div>
  );
};

export default App;
