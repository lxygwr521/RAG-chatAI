<template>
    <main class="flex justify-center items-center h-screen">
        <div class="loading"></div>     
    </main>
   
</template>
  
<script setup lang='ts'>
  
</script>
  
<style scoped lang="scss">
    .loading {
        width: 80px;
        height: 20px;
        mask: linear-gradient(90deg, #000 70%, #0000 0) left/20% 100%;
        background: linear-gradient(#000 0 0) left -25% top 0 /20% 100% no-repeat #ddd;
        animation: loading-37 1s infinite steps(6);
    }
    @keyframes loading-37  {
        100%  {
        background-position: right -25% top 0;
        }
    }
</style>