import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import LibraryScreen from '../screens/LibraryScreen';
import ReaderScreen from '../screens/ReaderScreen';
import AIScreen from '../screens/AIScreen';

const Stack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

function TabsRoot() {
  return (
    <Tabs.Navigator>
      <Tabs.Screen name="Library" component={LibraryScreen} />
    </Tabs.Navigator>
  );
}

export default function AppNavigator() {
  return (
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="Home" component={TabsRoot} options={{ headerShown: false }} />
        <Stack.Screen name="Reader" component={ReaderScreen} />
        <Stack.Screen name="AI" component={AIScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}