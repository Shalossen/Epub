import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { WebView } from 'react-native-webview';
import * as FileSystem from 'expo-file-system';
import { useRoute } from '@react-navigation/native';

// Basic inlined reader HTML with epub.js from unpkg
const readerHtml = (bookUri: string, theme: { bg: string; fg: string; fontSize: number; fontFamily: string; justify: boolean }, flow: 'paginated' | 'scrolled') => `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script src="https://unpkg.com/epubjs@0.3.88/dist/epub.min.js"></script>
  <style>
    body, html { margin:0; padding:0; height:100%; overflow:hidden; background:${theme.bg}; color:${theme.fg}; }
    #viewer { height: 100vh; }
  </style>
</head>
<body>
  <div id="viewer"></div>
  <script>
    const book = ePub(${JSON.stringify(bookUri)});
    const rendition = book.renderTo("viewer", { width: '100%', height: '100%', flow: ${JSON.stringify(flow)} });
    const theme = {
      'custom': {
        'background': ${JSON.stringify(theme.bg)},
        'color': ${JSON.stringify(theme.fg)},
        'font-size': ${JSON.stringify(theme.fontSize + 'px')},
        'font-family': ${JSON.stringify(theme.fontFamily)},
        ${theme.justify ? "'text-align': 'justify'," : ''}
      }
    };
    rendition.themes.register(theme);
    rendition.themes.select('custom');

    book.ready.then(() => rendition.display());

    window.addEventListener('message', (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'setTheme') {
          rendition.themes.register({ 'custom': msg.payload });
          rendition.themes.select('custom');
        } else if (msg.type === 'setFlow') {
          rendition.flow(msg.payload);
        } else if (msg.type === 'goTo') {
          rendition.display(msg.payload);
        }
      } catch (e) {}
    });

    // Table of contents
    book.loaded.navigation.then(nav => {
      const toc = nav.toc.map(i => ({ href: i.href, label: i.label }));
      window.ReactNativeWebView.postMessage(JSON.stringify({ type:'toc', payload: toc }));
    });
  </script>
</body>
</html>`;

export default function ReaderScreen() {
  const route = useRoute<any>();
  const { localUri, title } = route.params as { localUri: string; title: string };
  const [flow, setFlow] = useState<'paginated' | 'scrolled'>('paginated');
  const [fontSize, setFontSize] = useState(18);
  const [justify, setJustify] = useState(true);
  const [bg, setBg] = useState('#ffffff');
  const [fg, setFg] = useState('#111111');
  const [fontFamily, setFontFamily] = useState('serif');
  const webRef = useRef<WebView>(null);

  const html = useMemo(() => readerHtml(localUri, { bg, fg, fontSize, fontFamily, justify }, flow), [localUri, bg, fg, fontSize, fontFamily, justify, flow]);

  function post(type: string, payload: any) {
    webRef.current?.postMessage(JSON.stringify({ type, payload }));
  }

  return (
    <View style={styles.container}>
      <View style={styles.toolbar}>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
        <TouchableOpacity onPress={() => setFlow((f) => (f === 'paginated' ? 'scrolled' : 'paginated'))} style={styles.toolButton}>
          <Text style={styles.toolLabel}>{flow === 'paginated' ? 'Flow: Pages' : 'Flow: Scroll'}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setFontSize((s) => Math.max(12, s - 2))} style={styles.toolButton}><Text style={styles.toolLabel}>A-</Text></TouchableOpacity>
        <TouchableOpacity onPress={() => setFontSize((s) => Math.min(34, s + 2))} style={styles.toolButton}><Text style={styles.toolLabel}>A+</Text></TouchableOpacity>
        <TouchableOpacity onPress={() => setJustify((j) => !j)} style={styles.toolButton}><Text style={styles.toolLabel}>{justify ? 'Justify' : 'Ragged'}</Text></TouchableOpacity>
        <TouchableOpacity onPress={() => { setBg(bg === '#ffffff' ? '#0e1116' : '#ffffff'); setFg(fg === '#111111' ? '#e6edf3' : '#111111'); }} style={styles.toolButton}><Text style={styles.toolLabel}>Theme</Text></TouchableOpacity>
      </View>
      <WebView
        ref={webRef}
        originWhitelist={["*"]}
        source={{ html }}
        onMessage={(evt) => {
          // handle messages like toc
        }}
        onLoadEnd={() => {
          // sync settings on load
          post('setFlow', flow);
          post('setTheme', { background: bg, color: fg, 'font-size': fontSize + 'px', 'font-family': fontFamily, ...(justify ? { 'text-align': 'justify' } : {}) });
        }}
        style={{ flex: 1 }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  toolbar: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#ddd' },
  title: { flex: 1, fontWeight: '600' },
  toolButton: { paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#f0f2f4', borderRadius: 6 },
  toolLabel: { color: '#111' },
});