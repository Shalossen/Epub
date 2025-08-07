import AsyncStorage from '@react-native-async-storage/async-storage';

export type StoredBook = {
  id: string;
  title: string;
  fileUri: string;
  uploadedBookId?: string; // backend id
  createdAt: number;
};

const BOOKS_KEY = 'BOOKS_V1';
const CURRENT_BOOK_ID_KEY = 'CURRENT_BOOK_ID_V1';

export async function getBooks(): Promise<StoredBook[]> {
  const v = await AsyncStorage.getItem(BOOKS_KEY);
  return v ? (JSON.parse(v) as StoredBook[]) : [];
}

export async function saveBooks(books: StoredBook[]): Promise<void> {
  await AsyncStorage.setItem(BOOKS_KEY, JSON.stringify(books));
}

export async function addBook(book: StoredBook): Promise<void> {
  const books = await getBooks();
  books.unshift(book);
  await saveBooks(books);
}

export async function setCurrentBookId(id: string | null): Promise<void> {
  if (id) await AsyncStorage.setItem(CURRENT_BOOK_ID_KEY, id);
  else await AsyncStorage.removeItem(CURRENT_BOOK_ID_KEY);
}

export async function getCurrentBookId(): Promise<string | null> {
  return AsyncStorage.getItem(CURRENT_BOOK_ID_KEY);
}