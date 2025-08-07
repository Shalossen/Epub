import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, ScrollView } from 'react-native';
import * as FileSystem from 'expo-file-system';
import { useRoute } from '@react-navigation/native';

const SERVER = process.env.EXPO_PUBLIC_API_URL || 'http://127.0.0.1:8080';

async function uploadBook(uri: string) {
  const fileInfo = await FileSystem.getInfoAsync(uri);
  const form = new FormData();
  // @ts-ignore: RN uses uri and name
  form.append('file', { uri, name: 'book.epub', type: 'application/epub+zip' });
  const res = await fetch(`${SERVER}/upload`, {
    method: 'POST',
    body: form as any,
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) throw new Error('Upload failed');
  return res.json();
}

async function scanBook(bookId: string) {
  const res = await fetch(`${SERVER}/scan/${bookId}`, { method: 'POST' });
  if (!res.ok) throw new Error('Scan failed');
  return res.json();
}

async function getAnalysis(bookId: string) {
  const res = await fetch(`${SERVER}/analysis/${bookId}`);
  if (!res.ok) throw new Error('No analysis yet');
  return res.json();
}

export default function AIScreen() {
  const route = useRoute<any>();
  const { localUri } = route.params as { localUri: string };
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    try {
      setBusy(true);
      setError(null);
      const uploaded = await uploadBook(localUri);
      await scanBook(uploaded.book_id);
      const analysis = await getAnalysis(uploaded.book_id);
      setResult(analysis);
    } catch (e: any) {
      setError(e?.message || 'Failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.container}>
      <TouchableOpacity onPress={run} style={styles.button} disabled={busy}>
        <Text style={styles.buttonText}>{busy ? 'Processing...' : 'Run AI Analysis'}</Text>
      </TouchableOpacity>
      {busy && <ActivityIndicator style={{ marginTop: 12 }} />}
      {error && <Text style={{ color: 'red', marginTop: 12 }}>{error}</Text>}
      {result && (
        <ScrollView style={{ marginTop: 16 }} contentContainerStyle={{ paddingBottom: 80 }}>
          <Text style={styles.section}>Characters</Text>
          <Text>{(result.characters || []).join(', ') || '—'}</Text>
          <Text style={styles.section}>Top Keywords</Text>
          <Text>{(result.top_keywords || []).join(', ') || '—'}</Text>
          <Text style={styles.section}>Complexity</Text>
          <Text>{JSON.stringify(result.complexity, null, 2)}</Text>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', padding: 16 },
  button: { backgroundColor: '#1f6feb', padding: 12, borderRadius: 8, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '600' },
  section: { marginTop: 16, fontWeight: '700' },
});