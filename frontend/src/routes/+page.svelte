<script lang="ts">
	import { onMount } from 'svelte';
	import Hero from '$lib/components/Hero.svelte';
	import Demo from '$lib/components/Demo.svelte';
	import Problem from '$lib/components/Problem.svelte';
	import Stats from '$lib/components/Stats.svelte';
	import HowItWorks from '$lib/components/HowItWorks.svelte';
	import BeforeAfter from '$lib/components/BeforeAfter.svelte';
	import Pricing from '$lib/components/Pricing.svelte';
	import Testimonials from '$lib/components/Testimonials.svelte';
	import Faq from '$lib/components/Faq.svelte';
	import Cta from '$lib/components/Cta.svelte';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let scrollY = $state(0);

	onMount(() => {
		// Intersection observer for scroll animations
		const observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						entry.target.classList.add('animate-in');
					}
				});
			},
			{ threshold: 0.1, rootMargin: '0px 0px -50px 0px' }
		);

		document.querySelectorAll('.scroll-reveal').forEach((el) => observer.observe(el));
		return () => observer.disconnect();
	});
</script>

<svelte:window bind:scrollY />

<svelte:head>
	<title>ReviewRep — AI Review Responses for UK Businesses</title>
</svelte:head>

<div class="min-h-screen bg-[#050510] text-white overflow-hidden">
	<!-- Animated gradient orbs -->
	<div class="fixed inset-0 pointer-events-none overflow-hidden">
		<div class="absolute -top-40 -right-40 w-[600px] h-[600px] bg-blue-600/20 rounded-full blur-[120px] animate-pulse"></div>
		<div class="absolute top-1/2 -left-40 w-[500px] h-[500px] bg-violet-600/15 rounded-full blur-[120px]" style="animation: pulse 4s ease-in-out infinite 1s;"></div>
		<div class="absolute bottom-0 right-1/4 w-[400px] h-[400px] bg-cyan-600/10 rounded-full blur-[120px]" style="animation: pulse 5s ease-in-out infinite 2s;"></div>
	</div>

	<!-- Dot grid overlay -->
	<div class="fixed inset-0 pointer-events-none opacity-[0.03]" style="background-image: radial-gradient(circle, white 1px, transparent 1px); background-size: 30px 30px;"></div>

	<div class="relative z-10">
		<Nav {scrollY} />
		<Hero />
		<Demo />
		<Problem />
		<Stats />
		<HowItWorks />
		<BeforeAfter />
		<Testimonials />
		<Pricing />
		<Faq />
		<Cta />
		<Footer />
	</div>
</div>

<style>
	:global(.scroll-reveal) {
		opacity: 0;
		transform: translateY(30px);
		transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
	}
	:global(.scroll-reveal.animate-in) {
		opacity: 1;
		transform: translateY(0);
	}
	:global(.scroll-reveal-delay-1) { transition-delay: 0.1s; }
	:global(.scroll-reveal-delay-2) { transition-delay: 0.2s; }
	:global(.scroll-reveal-delay-3) { transition-delay: 0.3s; }
	:global(.scroll-reveal-delay-4) { transition-delay: 0.4s; }

	@keyframes pulse {
		0%, 100% { opacity: 0.3; transform: scale(1); }
		50% { opacity: 0.6; transform: scale(1.1); }
	}
</style>
