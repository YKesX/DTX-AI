import type { SidebarsConfig } from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    {
      type: 'doc',
      id: 'index',
      label: 'Overview',
    },
    {
      type: 'category',
      label: 'System Design',
      collapsed: false,
      items: ['architecture', 'repository-structure', 'services'],
    },
    {
      type: 'category',
      label: 'API and Schemas',
      collapsed: false,
      items: ['api-reference', 'data-models'],
    },
    {
      type: 'category',
      label: 'Frontend',
      collapsed: false,
      items: ['frontend'],
    },
    {
      type: 'category',
      label: 'AI and XAI',
      collapsed: false,
      items: ['ai-xai', 'validation-layer'],
    },
    {
      type: 'category',
      label: 'Hardware',
      collapsed: false,
      items: ['hardware-demo'],
    },
    {
      type: 'category',
      label: 'Operations',
      collapsed: false,
      items: ['environment', 'setup', 'deployment'],
    },
    {
      type: 'doc',
      id: 'known-issues',
      label: 'Known Issues',
    },
    {
      type: 'doc',
      id: 'glossary',
      label: 'Glossary',
    },
  ],
};

export default sidebars;
