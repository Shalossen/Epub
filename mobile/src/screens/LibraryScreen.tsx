import React, { useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { addBook, getBooks, StoredBook } from '../utils/storage';
import { useNavigation } from '@react-navigation/native';

export default function LibraryScreen() {
  const [books, setBooks] = useState<StoredBook[]>([]);
  const navigation = useNavigation<any>();

  useEffect(() => {
    (async () => setBooks(await getBooks()))();
  }, []);

  async function importEpub() {
    const res = await DocumentPicker.getDocumentAsync({ type: 'application/epub+zip', copyToCacheDirectory: true });
    if (res.canceled) return;
    const asset = res.assets?.[0];
    if (!asset) return;
    if (!asset.name.toLowerCase().endsWith('.epub')) {
      Alert.alert('Unsupported', 'Please select a .epub file');
      return;
    }
    const dest = `${FileSystem.documentDirectory}${Date.now()}_${asset.name}`;
    await FileSystem.copyAsync({ from: asset.uri, to: dest });
    const book: StoredBook = {
      id: String(Date.now()),
      title: asset.name.replace(/\.epub$/i, ''),
      fileUri: dest,
      createdAt: Date.now(),
    };
    await addBook(book);
    setBooks(await getBooks());
  }

  function openBook(book: StoredBook) {
    navigation.navigate('Reader', { localUri: book.fileUri, title: book.title, storedId: book.id });
  }

  const renderItem = ({ item }: { item: StoredBook }) => (
    <TouchableOpacity style={styles.item} onPress={() => openBook(item)}>
      <Text style={styles.title}>{item.title}</Text>
      <Text style={styles.meta}>{new Date(item.createdAt).toLocaleString()}</Text>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Library</Text>
        <TouchableOpacity onPress={importEpub} style={styles.button}>
          <Text style={styles.buttonText}>Import .epub</Text>
        </TouchableOpacity>
      </View>
      <FlatList
        data={books}
        keyExtractor={(b) => b.id}
        renderItem={renderItem}
        contentContainerStyle={{ paddingBottom: 24 }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  header: { padding: 16, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerTitle: { fontSize: 22, fontWeight: '600' },
  button: { backgroundColor: '#1f6feb', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  buttonText: { color: '#fff', fontWeight: '600' },
  item: { padding: 16, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: '#ddd' },
  title: { fontSize: 16, fontWeight: '500' },
  meta: { color: '#666', marginTop: 4 },
});