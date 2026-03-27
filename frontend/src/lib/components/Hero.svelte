<script lang="ts">
	import { onMount } from 'svelte';

	let visible = $state(false);
	let count1 = $state(0);
	let count2 = $state(0);
	let count3 = $state(0);

	onMount(() => {
		visible = true;
		// Animated counters
		const animate = (setter: (n: number) => void, target: number, duration: number) => {
			const start = performance.now();
			const step = (now: number) => {
				const progress = Math.min((now - start) / duration, 1);
				const eased = 1 - Math.pow(1 - progress, 3);
				setter(Math.round(eased * target));
				if (progress < 1) requestAnimationFrame(step);
			};
			requestAnimationFrame(step);
		};
		setTimeout(() => animate((n) => count1 = n, 10, 1500), 800);
		setTimeout(() => animate((n) => count2 = n, 89, 1500), 1000);
		setTimeout(() => animate((n) => count3 = n, 45, 1500), 1200);
	});
</script>

<section class="relative pt-32 pb-20 md:pt-44 md:pb-32 px-4">
	<div class="max-w-5xl mx-auto text-center">
		<!-- Badge -->
		<div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-sm text-white/60 mb-8 {visible ? 'animate-fade-up' : 'opacity-0'}" style="animation-delay: 0.1s;">
			<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
			Built for UK small businesses
		</div>

		<!-- Headline -->
		<h1 class="text-4xl md:text-7xl font-black leading-[1.05] tracking-tight mb-6 {visible ? 'animate-fade-up' : 'opacity-0'}" style="animation-delay: 0.2s;">
			Never write another<br>
			<span class="bg-gradient-to-r from-blue-400 via-violet-400 to-cyan-400 bg-clip-text text-transparent bg-[length:200%_auto] animate-gradient">review reply</span>
			again
		</h1>

		<!-- Sub -->
		<p class="text-lg md:text-xl text-white/40 max-w-2xl mx-auto mb-10 leading-relaxed {visible ? 'animate-fade-up' : 'opacity-0'}" style="animation-delay: 0.3s;">
			AI responds to every Google review in your brand's voice.<br class="hidden md:block">
			You click approve. 10 seconds. Done.
		</p>

		<!-- CTA -->
		<div class="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16 {visible ? 'animate-fade-up' : 'opacity-0'}" style="animation-delay: 0.4s;">
			<a href="/login" class="group relative px-8 py-4 rounded-2xl overflow-hidden font-semibold text-lg transition-all duration-300 hover:scale-[1.02] hover:shadow-[0_0_40px_rgba(99,102,241,0.3)]">
				<div class="absolute inset-0 bg-gradient-to-r from-blue-500 via-violet-500 to-blue-500 bg-[length:200%_100%] animate-gradient"></div>
				<span class="relative">Start Free — 7 Days</span>
			</a>
			<a href="#demo" class="px-8 py-4 rounded-2xl border border-white/10 text-white/60 hover:text-white hover:border-white/20 transition-all font-medium">
				See it in action
			</a>
		</div>

		<!-- Stats -->
		<div class="grid grid-cols-3 gap-4 md:gap-8 max-w-md mx-auto {visible ? 'animate-fade-up' : 'opacity-0'}" style="animation-delay: 0.6s;">
			<div class="text-center">
				<div class="text-3xl md:text-4xl font-bold text-white">{count1}s</div>
				<div class="text-xs md:text-sm text-white/30 mt-1">per reply</div>
			</div>
			<div class="text-center">
				<div class="text-3xl md:text-4xl font-bold text-white">{count2}%</div>
				<div class="text-xs md:text-sm text-white/30 mt-1">read replies</div>
			</div>
			<div class="text-center">
				<div class="text-3xl md:text-4xl font-bold text-white">+{count3}%</div>
				<div class="text-xs md:text-sm text-white/30 mt-1">more visits</div>
			</div>
		</div>
	</div>

	<!-- Scroll indicator -->
	<div class="absolute bottom-8 left-1/2 -translate-x-1/2 {visible ? 'animate-fade-up' : 'opacity-0'}" style="animation-delay: 1s;">
		<div class="w-6 h-10 rounded-full border-2 border-white/20 flex items-start justify-center p-1.5">
			<div class="w-1.5 h-3 bg-white/40 rounded-full animate-bounce"></div>
		</div>
	</div>
</section>

<style>
	@keyframes fade-up {
		from { opacity: 0; transform: translateY(30px); }
		to { opacity: 1; transform: translateY(0); }
	}
	@keyframes gradient {
		0% { background-position: 0% 50%; }
		50% { background-position: 100% 50%; }
		100% { background-position: 0% 50%; }
	}
	:global(.animate-fade-up) {
		animation: fade-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) both;
	}
	:global(.animate-gradient) {
		animation: gradient 4s ease-in-out infinite;
	}
</style>
