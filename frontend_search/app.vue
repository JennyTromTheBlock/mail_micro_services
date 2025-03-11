<template>
  <div class="h-screen w-full bg-blue-200">
    <div class="w-full bg-blue-500">
      <h1 class="text-white p-4 rounded-md mb-4 text-center">Hent Ordforekomster</h1>

    </div>


    <!-- Container for input og knap -->
    <div class="flex flex-col items-center justify-center h-2/3 p-4">
      <!-- Inputfelt til brugerens søgeord -->
      <input
          v-model="searchWord"
          type="text"
          placeholder="Indtast et ord..."
          class="border border-gray-300 p-2 rounded-md mb-4 w-64 text-center"
      />

      <!-- Knappen til at trigge GET-anmodningen -->
      <button
          @click="fetchWordOccurrences"
          class="bg-yellow-500 text-white py-2 px-4 rounded-md hover:bg-yellow-700 transition"
      >
        Hent Ordforekomster
      </button>

      <!-- Hvis listen ikke er tom, vis den -->
      <div v-if="occurrences.length > 0" class="mt-4">
        <h2 class="font-semibold">Forekomster:</h2>
        <ul class="list-disc mt-2">
          <li v-for="(occurrence, index) in occurrences" :key="index">
            File ID: {{ occurrence.file_id }}, Count: {{ occurrence.count }}
          </li>
        </ul>
      </div>

      <!-- Hvis listen er tom, vis en besked -->
      <div v-else class="mt-4 text-gray-500">
        <p>Ingen data fundet.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

// Ref til brugerens søgeord
const searchWord = ref("");

// Ref til at holde dataene
const occurrences = ref([]);

// Funktion der henter ordforekomsterne
const fetchWordOccurrences = async () => {
  try {
    if (!searchWord.value.trim()) {
      alert("Indtast et ord før du søger!");
      return;
    }

    // Brug fetch API til at sende GET-request til serveren med query parameteren
    const response = await fetch(
        `http://localhost:8003/word_occurrences/?word=${encodeURIComponent(searchWord.value)}`
    );

    // Tjek om requesten var succesfuld
    if (!response.ok) {
      throw new Error("Netværksfejl!");
    }

    // Parse JSON-dataen fra svaret
    const data = await response.json();

    // Gem den modtagne liste i occurrences
    occurrences.value = data;
  } catch (error) {
    console.error("Der opstod en fejl ved hentning af data:", error);
  }
};
</script>
