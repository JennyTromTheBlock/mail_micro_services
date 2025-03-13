<template>
  <div class="h-screen w-full bg-blue-200">
    <div class="w-full bg-blue-500">
      <h1 class="text-white p-4 rounded-md mb-4 text-center">Hent Ordforekomster</h1>
    </div>

    <div class="flex flex-col items-center justify-center h-2/3 p-4">
      <input
          v-model="searchWord"
          type="text"
          placeholder="Indtast et ord..."
          class="border border-gray-300 p-2 rounded-md mb-4 w-64 text-center"
      />

      <button
          @click="fetchWordOccurrences"
          class="bg-yellow-500 text-white py-2 px-4 rounded-md hover:bg-yellow-700 transition"
      >
        Hent Ordforekomster
      </button>

      <div v-if="occurrences.length > 0" class="mt-4">
        <h2 class="font-semibold">Forekomster:</h2>
        <ul class="list-disc mt-2">
          <li
              v-for="(occurrence, index) in occurrences"
              :key="index"
              @click="fetchFileContent(occurrence.file_id)"
              class="cursor-pointer text-blue-600 hover:underline"
          >
            File ID: {{ occurrence.file_id }}, Count: {{ occurrence.count }}
          </li>
        </ul>
      </div>

      <div v-else class="mt-4 text-gray-500">
        <p>Ingen data fundet.</p>
      </div>
    </div>

    <div v-if="selectedFile" class="fixed top-1/4 left-1/4 w-1/2 h-1/2 bg-white shadow-lg rounded-lg p-6 overflow-hidden">
      <button
          @click="closeFile"
          class="absolute top-2 right-2 bg-red-500 text-white px-3 py-1 rounded-md hover:bg-red-700"
      >
        X
      </button>
      <h3 class="font-bold text-lg">{{ selectedFile.file_name }}</h3>
      <div class="mt-2 p-2 bg-gray-100 rounded-md overflow-y-auto h-4/5 whitespace-pre-wrap">
        {{ selectedFile.content }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const searchWord = ref("");
const occurrences = ref([]);
const selectedFile = ref(null);

const fetchWordOccurrences = async () => {
  try {
    if (!searchWord.value.trim()) {
      alert("Indtast et ord før du søger!");
      return;
    }

    const response = await fetch(
        `http://localhost:8003/word_occurrences/?word=${encodeURIComponent(searchWord.value)}`
    );

    if (!response.ok) {
      throw new Error("Netværksfejl!");
    }

    occurrences.value = await response.json();
  } catch (error) {
    console.error("Der opstod en fejl ved hentning af data:", error);
  }
};

const fetchFileContent = async (fileId) => {
  try {
    const response = await fetch(`http://localhost:8003/file/${fileId}`);

    if (!response.ok) {
      throw new Error("Kunne ikke hente filindhold!");
    }

    selectedFile.value = await response.json();
  } catch (error) {
    console.error("Fejl ved hentning af fil:", error);
  }
};

const closeFile = () => {
  selectedFile.value = null;
};
</script>
