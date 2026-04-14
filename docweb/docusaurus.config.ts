import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'DTX-AI',
  tagline: 'Smart Warehouse Anomaly Detection with Explainable AI',
  favicon: 'img/favicon.ico',

  url: 'https://YKesX.github.io',
  baseUrl: '/DTX-AI/',

  organizationName: 'YKesX',
  projectName: 'DTX-AI',
  trailingSlash: false,

  onBrokenLinks: 'warn',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: { defaultLocale: 'en', locales: ['en'] },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          
          editUrl: 'https://github.com/YKesX/DTX-AI/tree/main/website/',
        },
        blog: false,
        theme: { customCss: './src/css/custom.css' },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      defaultMode: 'light',
      disableSwitch: true,
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: 'DTX-AI',
      logo: { alt: 'DTX-AI Logo', src: 'img/logo.svg' },
      items: [
        { type: 'docSidebar', sidebarId: 'docsSidebar', position: 'left', label: 'Docs' },
        { href: 'https://github.com/YKesX/DTX-AI', label: 'GitHub', position: 'right' },
      ],
    },
    footer: {
      links: [
        {
          title: 'Documentation',
          items: [
            { label: 'Overview', to: '/' },
            { label: 'Architecture', to: '/docs/architecture' },
            { label: 'API Reference', to: '/docs/api-reference' },
          ],
        },
        {
          title: 'Project',
          items: [
            { label: 'GitHub', href: 'https://github.com/YKesX/DTX-AI' },
            { label: 'Atılım University', href: 'https://www.atilim.edu.tr' },
          ],
        },
      ],
      copyright: `© ${new Date().getFullYear()} DTX-AI — Atılım University Computer Engineering Graduation Project`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.github,
      additionalLanguages: ['python', 'bash', 'json', 'typescript'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
