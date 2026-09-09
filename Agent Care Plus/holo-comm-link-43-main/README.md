# Serah Core AI

Act as an Expert Frontend Engineer and UI/UX Designer specializing in cinematic, sci-fi interfaces. I need you to write the complete code for a futuristic AI conversational frontend application. 

Use the following tech stack: React (Next.js), Tailwind CSS for styling, Framer Motion for complex animations, and Lucide React for icons. 

The application must have a dark, sleek cyberpunk/sci-fi aesthetic (think Iron Man's JARVIS or Ex Machina) and include the following features:

1. Layout & Architecture

- A full-screen, dark mode dashboard with a subtle animated grid or hex background.

- Main Central Area: The primary conversational interface.

- Right Sidebar (30% width): A "Diagnostics & Telemetry" panel showing the AI's internal processes.

2. The AI Voice Orb (Main Area - Center)

- A highly animated, glowing circular orb that represents the AI. 

- Default state: A slow, gentle pulse.

- Listening state: Expands slightly with a cyan/blue glow when the user speaks.

- Speaking state: Rapidly pulses and shifts colors (e.g., cyan to electric purple) synchronized to an audio visualizer effect using Framer Motion. Apply heavy box-shadow glows.

3. Chat Interface (Main Area - Bottom)

- A sleek, glassmorphic chat interface below the orb.

- User messages: Clean, right-aligned, monospace typography.

- AI messages: Left-aligned, typing-effect animation.

- Include a futuristic microphone button that toggles the "Listening" state.

4. "Thinking" Diagnostics Sidebar (Right Panel)

- This panel must look like complex AI processing telemetry.

- Include a scrolling terminal log showing simulated input/output data (e.g., "Parsing audio buffer...", "NLP extraction complete", "Querying neural net...").

- Include 1-2 futuristic diagram UI elements: A sine-wave audio visualizer, or a node-connection graph (use SVG or simulated CSS animations to make pulsing nodes and connecting lines).

- Text in this panel should use a monospace font (like Fira Code or Roboto Mono) in terminal green or electric cyan.

5. Styling & Polish details

- Color Palette: Deep obsidian/slate background (#09090b), electric cyan (#06b6d4), neon purple (#8b5cf6), and stark white for primary text.

- Use extensive glassmorphism (backdrop-blur, semi-transparent borders).

- Make sure to use Framer Motion `<motion.div>` for all layout transitions, orb glowing effects, and smooth sidebar data entry. 

Please provide the complete, functional React code in a single file (or clear component breakdown) with mock data and state management handling the toggling of "Listening" and "Speaking" states.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/1d1ff8ed-64da-4eed-ac31-ac5858d7f364).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
