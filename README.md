# Devliqly: AI Agents Website

Marketing site for [Devliqly](https://www.devliqly.in), an AI agent studio offering chatbot integration, customer service agents, inbound & outbound call agents, voice agents and custom agent workflows.

Built with React + Vite, GSAP ScrollTrigger and Lenis smooth scrolling.

## Development

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build in dist/
```

## Where things live

- `src/data.js`: all copy (services, process, stats, testimonials, FAQ, contact)
- `src/components/`: one component per section
- `src/index.css`: styles; the colour palette is set by the tokens at the top (`--accent-rgb`, `--accent-2-rgb`)
- `src/components/HeroField.jsx`: interactive dot-field background in the hero
