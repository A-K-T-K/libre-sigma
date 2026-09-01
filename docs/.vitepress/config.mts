import { defineConfig } from 'vitepress';
import mathjax3 from 'markdown-it-mathjax3';

export default defineConfig({
  title: 'LibRE Sigma',
  description: 'Open-Source Statistical Analysis & Reliability Engineering Platform',
  base: '/libre-sigma/',
  cleanUrls: true,
  lastUpdated: true,

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#008450' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'LibRE Sigma - Statistical Analysis & Reliability Engineering' }],
    ['meta', { property: 'og:description', content: 'Modern, open-source alternative to Minitab and JMP. Local-first Six Sigma, SPC, Taguchi DOE, and Weibull life data analysis.' }],
    ['meta', { property: 'og:image', content: '/main_window.png' }],
  ],

  markdown: {
    lineNumbers: true,
    config: (md) => {
      md.use(mathjax3);
    },
  },

  themeConfig: {
    logo: '/logo.svg',
    siteTitle: 'LibRE Sigma',

    nav: [
      { text: 'Overview', link: '/' },
      { text: 'How to Use', link: '/how-to-use' },
      { text: 'Architecture', link: '/architecture' },
      {
        text: 'Capabilities',
        items: [
          { text: 'Basic Statistics & Inference', link: '/capabilities/basic-statistics' },
          { text: 'SPC & Quality Engineering', link: '/capabilities/spc-quality' },
          { text: 'Design of Experiments (DOE)', link: '/capabilities/doe' },
          { text: 'Reliability & Survival Analysis', link: '/capabilities/reliability' },
        ],
      },
      { text: 'Plugin Guide', link: '/plugin-guide' },
      { text: 'v1.0.0', items: [
        { text: 'Releases & Changelog', link: 'https://github.com/A-K-T-K/libre-sigma/releases' },
        { text: 'Source Code', link: 'https://github.com/A-K-T-K/libre-sigma' },
      ]},
    ],

    sidebar: [
      {
        text: 'Getting Started',
        collapsed: false,
        items: [
          { text: 'Platform Overview', link: '/' },
          { text: 'How to Use LibRE Sigma', link: '/how-to-use' },
          { text: 'System Architecture', link: '/architecture' },
        ],
      },
      {
        text: 'Statistical Capabilities',
        collapsed: false,
        items: [
          { text: 'Basic Statistics & Inference', link: '/capabilities/basic-statistics' },
          { text: 'SPC & Quality Engineering', link: '/capabilities/spc-quality' },
          { text: 'Design of Experiments (DOE)', link: '/capabilities/doe' },
          { text: 'Reliability & Life Data Analysis', link: '/capabilities/reliability' },
        ],
      },
      {
        text: 'Developer & Extensions',
        collapsed: false,
        items: [
          { text: 'Plugin Development Guide', link: '/plugin-guide' },
        ],
      },
    ],

    search: {
      provider: 'local',
      options: {
        detailedView: true,
      },
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/A-K-T-K/libre-sigma' },
    ],

    editLink: {
      pattern: 'https://github.com/A-K-T-K/libre-sigma/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Released under the MIT License. Zero cloud tracking, 100% local-first.',
      copyright: 'Copyright © 2026 LibRE Sigma Contributors & Developers.',
    },

    docFooter: {
      prev: 'Previous Page',
      next: 'Next Page',
    },
  },
});
