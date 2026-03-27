<script lang="ts">
	let { scrollY = 0 }: { scrollY: number } = $props();
	let menuOpen = $state(false);
	let scrolled = $derived(scrollY > 50);
</script>

<nav class="fixed top-0 left-0 right-0 z-50 transition-all duration-500 {scrolled ? 'bg-[#050510]/80 backdrop-blur-xl border-b border-white/5' : ''}">
	<div class="max-w-6xl mx-auto px-4 md:px-6 py-4 flex justify-between items-center">
		<a href="/" class="text-xl font-bold tracking-tight">
			Review<span class="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">Rep</span>
		</a>

		<div class="hidden md:flex items-center gap-8 text-sm">
			<a href="#demo" class="text-white/50 hover:text-white transition">Demo</a>
			<a href="#pricing" class="text-white/50 hover:text-white transition">Pricing</a>
			<a href="#faq" class="text-white/50 hover:text-white transition">FAQ</a>
			<a href="/login" class="group relative px-5 py-2.5 rounded-full overflow-hidden">
				<div class="absolute inset-0 bg-gradient-to-r from-blue-500 to-violet-500 transition-all duration-300 group-hover:opacity-90"></div>
				<span class="relative font-medium text-sm">Get Started</span>
			</a>
		</div>

		<button onclick={() => menuOpen = !menuOpen} class="md:hidden p-2">
			<svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				{#if menuOpen}
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
				{:else}
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
				{/if}
			</svg>
		</button>
	</div>

	{#if menuOpen}
		<div class="md:hidden bg-[#050510]/95 backdrop-blur-xl border-t border-white/5 px-4 py-4 space-y-3">
			<a href="#demo" class="block text-white/60 hover:text-white py-2" onclick={() => menuOpen = false}>Demo</a>
			<a href="#pricing" class="block text-white/60 hover:text-white py-2" onclick={() => menuOpen = false}>Pricing</a>
			<a href="#faq" class="block text-white/60 hover:text-white py-2" onclick={() => menuOpen = false}>FAQ</a>
			<a href="/login" class="block bg-gradient-to-r from-blue-500 to-violet-500 text-center py-2.5 rounded-xl font-medium" onclick={() => menuOpen = false}>Get Started</a>
		</div>
	{/if}
</nav>
