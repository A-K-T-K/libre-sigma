import DefaultTheme from 'vitepress/theme';
import './custom.css';

export default {
  extends: DefaultTheme,
  enhanceApp({ app, router, siteData }) {
    // register global components if needed
  },
};
